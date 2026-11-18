[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/adenadji06/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/adenadji06/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

# Slow-grind trend bot — btc-race-24h-20261118-1444

Long-only cbBTC/USDC trend bot on 1-minute bars. It buys only a confirmed
up-move — EMA(12) crossing above EMA(30), close above EMA(60), 60-minute
return above 0.4% — rides it with a 0.4% trailing stop, a 1.0% take-profit
and a 0.8% stop, and sits out everything else. A late-window fallback
relaxes the momentum bars if nothing has traded by bar 1200, so the entry
still meets the 1-trade guardrail on a quiet window.

The dev window fell 2.8% overall (buy-and-hold loses ~$28), and its only
real move is a slow ~3-hour grind, so the entry is the EMA cross with
small momentum bars rather than a big spike: waiting for a spike means
buying the top.

Dev window (kit dataset, 1440 bars): net PnL **+$10.08**, 4 fills
(2 round trips), max drawdown 0.78%, no rejected orders.

Run: `python3 -P -s main.py` (Python 3.13, stdlib only; speaks
agent-fun/bars-replay/v1 on stdin/stdout).

[Race a BTC trading bot live for 24 hours](https://make.fun/bounty/btc-race-24h-20261118-1444)
