# moomoo-bot

CUI-first trading bot prototype for Moomoo US stocks and ETFs.

This repository is for strategy research/backtests and local-only paper simulation. Broker API order submission (both REAL and SIMULATE) is intentionally disabled.

## Setup

```bash
python -m pip install -e .[dev]
```

For the local UI paper simulator (no moomoo dependency for order execution):

```bash
python -m pip install -e .[dev,ui]
streamlit run src/moomoo_bot/ui/paper_studio.py
```

## Commands

```bash
moomoo-bot --help
moomoo-bot status
moomoo-bot execution-report --fills-limit 20 --realizations-limit 20
moomoo-bot research --history-days 2200
moomoo-bot satellite --history-days 2200 --satellite-weights 0.05,0.10,0.15,0.20,0.25
moomoo-bot paper-run --history-days 2200
moomoo-bot paper-trade --local-sim --history-days 2200
moomoo-bot auto-run --history-days 2200
moomoo-bot backtest --min-holding-days 21
moomoo-bot verify-api --history-days 2200
pytest
```

On Windows, you can also double-click a batch file from the repository root to run the bot:

- `run-paper-trade.bat` runs the local PaperSimulator; it does not submit broker orders.
- `moomoo-bot auto-run` / `moomoo-bot autopilot` run the local PaperSimulator; `run-paper-studio.bat` opens the local simulation UI.

The `paper-trade` command records orders in the local PaperSimulator only. There is no broker API order-submission path exposed by the CLI.

The paper workflow has two steps: `paper-run` prints the target rebalance plan, and `paper-trade --local-sim` records virtual fills in the local PaperSimulator.

Broker API order submission is disabled:

- `live-trade` always exits before loading settings or creating a broker client.
- `paper-trade` uses the local PaperSimulator only.
- `auto-run` and `autopilot` use local simulation and do not create a Moomoo trade client.
- `paper-repair` is disabled because it submits broker API SIMULATE repair orders.
- `run-live-trade.bat` is a disabled stub.
- No REAL or SIMULATE broker orders are sent by the supported CLI workflows.

Local paper simulation persists risk/equity state under `~/.moomoo_bot/paper-sim-state.db` and simulator balances under `~/.moomoo_bot/paper-sim-state.json`. The CLI does not create or use a live trading state for order execution.
The daily loss limit is evaluated against the most recent persisted prior-market-date equity snapshot.
Normal order flow also enforces a persisted daily order cap, so a buggy loop cannot keep submitting non-liquidation orders forever across repeated auto-run cycles.
Use `moomoo-bot execution-report` to inspect recent fills, fees, slippage, pending orders, and realized PnL from the mode-specific persisted state DB. If you need a fixed location, set `MOOMOO_BOT_STATE_DB_PATH` explicitly.

Paper-trading capital is entered in JPY by default and converted to USD for US-stock sizing using the configured JPY/USD rate. The default `100000` in the Windows batch files now means 100,000 JPY, not 100,000 USD.

You can override the conversion rate in either of these ways:

- Environment variable: `MOOMOO_BOT_FX_JPY_PER_USD=155.5`
- CLI input: `--fx-jpy-per-usd 155.5`

Backtest defaults are separated from paper-trade defaults. The backtest command now auto-searches the momentum configuration and benchmark blend, prints the best result, and lists the top candidates.

Recommended backtest command:

```bash
moomoo-bot backtest --min-holding-days 21
```

If you want a fixed blend instead of auto-search, pass `--satellite-weight 1.0` for the pure active sleeve or another weight between 0 and 1.

The current cost-aware real-data research leader is a monthly long-only momentum rotation across liquid US large-cap stocks with a 252-day lookback, 252-day trend filter, top 2 holdings, no skip window, and a 21-trading-day rebalance.
The same active sleeve also works as a satellite over VT, but the latest real-data validation no longer favors the old 23% setting. The best balanced sleeve now sits around 43% to 45% active, while 23% to 25% remains a more conservative but less competitive blend and 100% active stays a higher-return, higher-risk option.
Those validated defaults now match the runtime profile: top 2, skip 0, and a 45% active sleeve by default unless you override them explicitly.
If you are upgrading from an older setup, review your local `.env` overrides as well. Stale values there still win over the validated defaults and can silently put you back on the old profile.

## Notes

- Moomoo OpenD may be used for market data; the supported CLI workflows do not submit broker orders.
- Strategy outperformance against ACWI/VT is a research goal, not a guarantee.
- Secrets must stay in environment variables.
- Run `moomoo-bot status` before simulation to confirm the active sleeve, cost profile, daily order cap, resolved state DB path, and any validated-profile drift match your intended setup.
- Run `moomoo-bot execution-report` after local paper simulations to audit fills, fees, slippage, and realized PnL.
- The latest 2026-04-24 real-data validation with 2 bps transaction costs points to 252/252 top-2 skip-0 as the current robustness leader.
- The latest satellite validation favors roughly 43% to 45% active over VT for the best balanced profile. The older 23% to 25% sleeve is still positive, but it is no longer the current best result.
- See docs/real_data_validation_2026-04-24.md for the exact commands and metrics behind the current claim set.
- See [docs/operations.md](docs/operations.md) for the operational runbook.
