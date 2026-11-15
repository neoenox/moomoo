"""Trading CLI commands module.

Purpose: Local paper simulation, auto-monitor, and autopilot commands.
         Uses deferred imports from moomoo_bot.cli for monkeypatch compatibility.
Related: _cli_app.py, cli.py, orchestrator/.
"""

from __future__ import annotations

import typer
from moomoo import TrdEnv

from moomoo_bot._cli_app import app, cli_module
from moomoo_bot import orchestrator


def _require_paper_mode(settings, command_name: str) -> None:
    if settings.execution_mode != "paper":
        raise typer.BadParameter(
            f"{command_name} requires MOOMOO_BOT_EXECUTION_MODE=paper"
        )


@app.command()
def paper_run(
    symbols: str | None = typer.Option(
        None, help="Comma-separated US symbols to trade."
    ),
    benchmark_symbol: str | None = typer.Option(
        None, help="Benchmark symbol used for market data alignment."
    ),
    history_days: int = typer.Option(
        2200, min=60, help="Calendar lookback window for historical data."
    ),
    capital: float | None = typer.Option(
        None,
        min=5.0,
        help="Override input capital used for sizing the paper rebalance (JPY by default).",
    ),
    fx_jpy_per_usd: float | None = typer.Option(
        None, min=0.01, help="JPY per USD used to convert paper capital for sizing."
    ),
    minimum_order_value: float = typer.Option(
        5.0, min=0.0, help="Minimum order value used for fractional sizing."
    ),
) -> None:
    from moomoo_bot.cli_helpers import parse_symbols as _parse_symbols

    _cli = cli_module()
    settings = _cli.get_settings()
    _require_paper_mode(settings, "paper-run")
    orchestrator.run_one_shot_trade(
        settings=settings,
        trade_env=TrdEnv.SIMULATE,
        symbols=_parse_symbols(symbols) or settings.symbol_list,
        benchmark_symbol=benchmark_symbol or settings.benchmark_symbol,
        history_days=history_days,
        capital=capital,
        fx_jpy_per_usd=fx_jpy_per_usd,
        minimum_order_value=minimum_order_value,
        max_position_weight=settings.live_max_position_weight,
        submit_orders=False,
    )


@app.command()
def paper_trade(
    symbols: str | None = typer.Option(
        None, help="Comma-separated US symbols to trade."
    ),
    benchmark_symbol: str | None = typer.Option(
        None, help="Benchmark symbol used for market data alignment."
    ),
    history_days: int = typer.Option(
        2200, min=60, help="Calendar lookback window for historical data."
    ),
    capital: float | None = typer.Option(
        None,
        min=5.0,
        help="Override input capital used for sizing the paper rebalance (JPY by default).",
    ),
    fx_jpy_per_usd: float | None = typer.Option(
        None, min=0.01, help="JPY per USD used to convert paper capital for sizing."
    ),
    minimum_order_value: float = typer.Option(
        5.0, min=0.0, help="Minimum order value used for fractional sizing."
    ),
    local_sim: bool = typer.Option(
        True,
        "--local-sim",
        help="Use the local PaperSimulator; broker API order submission is disabled.",
    ),
) -> None:
    from moomoo_bot.cli_helpers import parse_symbols as _parse_symbols

    _cli = cli_module()
    settings = _cli.get_settings()
    _require_paper_mode(settings, "paper-trade")
    if not local_sim:
        raise typer.BadParameter(
            "Broker API SIMULATE order submission is disabled; use --local-sim."
        )
    orchestrator.run_one_shot_trade(
        settings=settings,
        trade_env=TrdEnv.SIMULATE,
        symbols=_parse_symbols(symbols) or settings.symbol_list,
        benchmark_symbol=benchmark_symbol or settings.benchmark_symbol,
        history_days=history_days,
        capital=capital,
        fx_jpy_per_usd=fx_jpy_per_usd,
        minimum_order_value=minimum_order_value,
        max_position_weight=settings.live_max_position_weight,
        use_local_sim=True,
    )


@app.command()
def paper_repair(
    benchmark_symbol: str | None = typer.Option(None, help="Disabled."),
    clear_local_state: bool = typer.Option(
        True,
        "--clear-local-state/--keep-local-state",
        help="Disabled; no broker repair orders are submitted.",
    ),
) -> None:
    """Disabled safety stub; repair previously submitted API paper orders manually."""
    raise typer.BadParameter(
        "paper-repair is disabled because it submits broker API SIMULATE orders. "
        "No broker repair action is permitted in this project."
    )


@app.command()
def live_trade(
    symbols: str | None = typer.Option(None, help="Disabled."),
    benchmark_symbol: str | None = typer.Option(None, help="Disabled."),
    history_days: int = typer.Option(2200, min=60, help="Disabled."),
    capital: float | None = typer.Option(None, min=5.0, help="Disabled."),
    fx_jpy_per_usd: float | None = typer.Option(None, min=0.01, help="Disabled."),
    minimum_order_value: float = typer.Option(5.0, min=0.0, help="Disabled."),
    confirm_live_trading: bool = typer.Option(
        False, "--confirm-live-trading", help="Live trading is disabled."
    ),
) -> None:
    """Disabled safety stub; this project does not submit REAL broker orders."""
    raise typer.BadParameter(
        "live-trade is disabled. Use backtests and the local PaperSimulator; "
        "broker REAL orders are not permitted in this project."
    )


@app.command()
def auto_run(
    symbols: str | None = typer.Option(
        None, help="Comma-separated US symbols to trade."
    ),
    benchmark_symbol: str | None = typer.Option(
        None, help="Benchmark symbol used for market data alignment."
    ),
    history_days: int = typer.Option(
        2200, min=60, help="Calendar lookback window for historical data."
    ),
    capital: float | None = typer.Option(
        None,
        min=5.0,
        help="Override input capital used for sizing the paper rebalance (JPY by default).",
    ),
    fx_jpy_per_usd: float | None = typer.Option(
        None, min=0.01, help="JPY per USD used to convert paper capital for sizing."
    ),
    minimum_order_value: float = typer.Option(
        5.0, min=0.0, help="Minimum order value used for fractional sizing."
    ),
    poll_seconds: int = typer.Option(
        900, min=60, help="Seconds to wait between monitoring cycles."
    ),
    max_consecutive_failures: int = typer.Option(
        5, min=1, help="Maximum consecutive failed cycles before auto-run stops."
    ),
) -> None:
    from moomoo_bot.cli_helpers import parse_symbols as _parse_symbols

    _cli = cli_module()
    settings = _cli.get_settings()
    _require_paper_mode(settings, "auto-run")
    orchestrator.run_auto_monitor(
        settings=settings,
        symbols=_parse_symbols(symbols) or settings.symbol_list,
        benchmark_symbol=benchmark_symbol or settings.benchmark_symbol,
        history_days=history_days,
        capital=capital,
        fx_jpy_per_usd=fx_jpy_per_usd,
        minimum_order_value=minimum_order_value,
        poll_seconds=poll_seconds,
        max_consecutive_failures=max_consecutive_failures,
        max_position_weight=settings.live_max_position_weight,
    )


@app.command()
def autopilot() -> None:
    """Start fully automated paper-trading loop using .env defaults only."""
    from moomoo_bot.cli_render import console

    _cli = cli_module()
    settings = _cli.get_settings()
    _require_paper_mode(settings, "autopilot")
    console.print("[bold green]Autopilot mode started[/bold green]")
    console.print(
        "Using .env defaults: symbols, benchmark, risk limits, webhook, health check."
    )
    orchestrator.run_auto_monitor(
        settings=settings,
        symbols=settings.symbol_list,
        benchmark_symbol=settings.benchmark_symbol,
        history_days=settings.autopilot_history_days,
        capital=settings.initial_capital,
        fx_jpy_per_usd=settings.fx_jpy_per_usd,
        minimum_order_value=settings.autopilot_minimum_order_value,
        poll_seconds=settings.autopilot_poll_seconds,
        max_consecutive_failures=settings.autopilot_max_consecutive_failures,
        max_position_weight=settings.live_max_position_weight,
    )
