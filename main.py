"""Long-only cbBTC/USDC trend bot for make.fun btc-race-24h-20261118-1444.

Strategy, tuned on the kit's frozen 24h dev window (1,440 one-minute bars
of cbBTC/USDC; BTC fell 2.8% over it, so buy-and-hold loses):
  - Buy only a confirmed up-move: EMA(12) crosses above EMA(30), the close
    is above EMA(60), and the 60-minute return is above 0.4% (with a
    0.3% floor on the same window). The dev window's only real move is a
    slow ~3h grind, so the momentum bars are small and the entry is the
    cross, not a level: waiting for a big spike means buying the top.
  - Ride it with a 0.4% trailing stop, a 1.0% take-profit and a 0.8% stop
    under the fill price; exit also on an EMA(12) cross back under EMA(30).
  - One position at a time, full cash on entry, nothing in the last 60
    bars (the replay flattens at the last close, so a late entry has no
    room to pay its ~26 bps round-trip cost).
  - Sit out everything else: cash earns 0, but a bad trade loses money.

Protocol: agent-fun/bars-replay/v1, spoken through the kit's vendored
Python shim (vendor/makefun_bars.py). Deterministic: no clock, no network,
no files outside the repo, no randomness; every decision is a pure
function of the bars seen so far. Prices are integers at price_scale 5;
EMA state is floats updated in a fixed order, so two runs on the same
data produce byte-identical replies.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- Strategy parameters (swept on the dev window; broad plateau, not a point) ---
FAST_SPAN = 12          # fast EMA
SLOW_SPAN = 30          # slow EMA
TREND_SPAN = 60         # long EMA the close must sit above
MOM_WIN = 60            # momentum window, in bars
MOM_MIN = 0.003         # 60-min return floor
MOM60_MIN = 0.004       # 60-min return bar (binding: stricter than MOM_MIN)
TRAIL = 0.004           # trailing stop, share below the peak close
TAKE_PROFIT = 0.01      # take profit, share above the fill price
STOP_LOSS = 0.008       # stop loss, share below the fill price
MAX_SLIPPAGE_BPS = 100  # 1%: fills cost ~9 bps over the open, so this rarely binds
NO_TAIL_BARS = 60       # do not open a position this close to the window end
WINDOW_BARS = 1440      # bars per window (dev and race alike)
# Late-window fallback: the race window is a different 24h, and an entry
# that never trades fails the guardrails (at least 1 trade) outright.
# If nothing has traded by bar 1200, relax the momentum bars a little so
# a weaker up-move still gets taken; the cross and trend filters stay.
FALLBACK_BAR = 1200
FB_MOM_MIN = 0.002
FB_MOM60_MIN = 0.003


class Ema:
    """EMA seeded with the simple average of its first `span` closes,
    exactly like a textbook EMA warm-up; keeps the previous value so the
    bot can detect crosses."""

    def __init__(self, span):
        self.span = span
        self.k = 2.0 / (span + 1)
        self.warm = []
        self.value = None
        self.prev = None

    def update(self, close):
        self.prev = self.value
        if self.value is None:
            self.warm.append(close)
            if len(self.warm) == self.span:
                self.value = sum(self.warm) / self.span
        else:
            self.value += self.k * (close - self.value)
        return self.value


class Bot:
    def __init__(self):
        self.closes = []            # closes seen, oldest first
        self.fast = Ema(FAST_SPAN)
        self.slow = Ema(SLOW_SPAN)
        self.trend = Ema(TREND_SPAN)
        self.entry_px = 0           # fill price of the open position (0 = flat)
        self.peak_px = 0            # highest close since entry
        self.ever_traded = False

    def on_batch(self, state, batch):
        bar = None
        for b in batch["bars"]:
            if b["symbol"] == SYMBOL:
                bar = b
                break
        if bar is None:
            return []
        close = int(bar["c"])
        self.closes.append(close)
        fast = self.fast.update(close)
        slow = self.slow.update(close)
        trend = self.trend.update(close)

        # Learn the fill price of any buy that landed on this bar's open.
        for fill in batch["fills"]:
            if fill.get("status") == "filled" and fill.get("symbol") == SYMBOL:
                if fill["side"] == "buy":
                    self.entry_px = int(fill["price"])
                    self.peak_px = self.entry_px
                    self.ever_traded = True
                elif fill["side"] == "sell":
                    self.entry_px = 0
                    self.peak_px = 0

        holding = state.positions.get(SYMBOL)
        qty = holding.qty if holding is not None else 0

        if qty > 0:
            if close > self.peak_px:
                self.peak_px = close
            cross_down = (
                fast is not None and slow is not None
                and self.fast.prev is not None and self.slow.prev is not None
                and fast < slow and self.fast.prev >= self.slow.prev
            )
            trail_hit = close < self.peak_px * (1.0 - TRAIL)
            tp_hit = self.entry_px > 0 and close >= self.entry_px * (1.0 + TAKE_PROFIT)
            stop_hit = self.entry_px > 0 and close < self.entry_px * (1.0 - STOP_LOSS)
            if cross_down or trail_hit or tp_hit or stop_hit:
                return [{
                    "side": "sell",
                    "symbol": SYMBOL,
                    "qty": qty,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }]
            return []

        # Flat: look for an entry. Never trade warm-up batches, and never
        # open a position too close to the end of the window.
        if state.warming_up:
            return []
        if len(self.closes) >= WINDOW_BARS - NO_TAIL_BARS:
            return []
        if fast is None or slow is None or trend is None:
            return []
        if self.fast.prev is None or self.slow.prev is None:
            return []
        cross_up = fast > slow and self.fast.prev <= self.slow.prev
        if not cross_up:
            return []
        if close <= trend:
            return []
        n = len(self.closes)
        if n <= MOM_WIN:
            return []
        ref = self.closes[n - 1 - MOM_WIN]
        mom_min = MOM_MIN
        mom60_min = MOM60_MIN
        if not self.ever_traded and n >= FALLBACK_BAR:
            mom_min = FB_MOM_MIN
            mom60_min = FB_MOM60_MIN
        if close <= ref * (1.0 + mom_min):
            return []
        if close <= ref * (1.0 + mom60_min):
            return []
        cash = state.cash
        if cash < 1_000_000:  # below the 1 USDC minimum notional
            return []
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": cash,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]


def main():
    makefun_bars.run(Bot().on_batch)


if __name__ == "__main__":
    main()
