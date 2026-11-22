from __future__ import annotations

from pathlib import Path

import pytest

from moomoo_bot.paper_simulator import PaperSimulator, PaperStateCorruptError


@pytest.mark.parametrize(
    "invalid",
    [
        b"",
        b"{",
        b"[]",
        b"{}",
        b'{"cash": "not-a-number", "positions": {}, "trades": [], "equity_curve": []}',
        b'{"cash": 100, "positions": [], "trades": [], "equity_curve": []}',
        b'{"cash": 100, "positions": {}, "trades": [{}], "equity_curve": []}',
        bytes([0xFF]),
        b'{"cash": NaN, "positions": {}, "trades": [], "equity_curve": []}',
        b'{"cash": Infinity, "positions": {}, "trades": [], "equity_curve": []}',
        b'{"cash": 100, "positions": {"US.AAPL": {"quantity": NaN, "avg_cost": 10}}, "trades": [], "equity_curve": []}',
        b'{"cash": 100, "positions": {}, "trades": [{"trade_id": 1, "timestamp": "t", "symbol": "US.AAPL", "side": "BUY", "quantity": 1, "price": Infinity, "notional": 10, "realized_pnl": 0}], "equity_curve": []}',
        b'{"cash": 100, "positions": {}, "trades": [], "equity_curve": [{"timestamp": "t", "cash": 100, "market_value": 1, "equity": -Infinity, "unrealized_pnl": 0, "realized_pnl": 0}]}',
        b'{"cash": 100, "positions": {}, "trades": [], "equity_curve": [{"timestamp": "t", "cash": 100, "market_value": 1, "equity": 100, "unrealized_pnl": 0, "realized_pnl": NaN}]}',
    ],
)
def test_corrupt_existing_state_fails_closed(tmp_path: Path, invalid: bytes) -> None:
    state = tmp_path / "paper-sim-state.json"
    state.write_bytes(invalid)
    with pytest.raises(PaperStateCorruptError, match="paper simulator state"):
        PaperSimulator.load(state_path=state)
    assert state.read_bytes() == invalid


def test_missing_state_can_still_be_initialized(tmp_path: Path) -> None:
    state = tmp_path / "paper-sim-state.json"
    simulator = PaperSimulator.load(state_path=state, initial_cash=234.0)
    assert simulator.cash == 234.0
    simulator.save()
    assert PaperSimulator.load(state_path=state).cash == 234.0
    assert not list(tmp_path.glob("*.tmp"))


def test_existing_trades_survive_round_trip(tmp_path: Path) -> None:
    state = tmp_path / "paper-sim-state.json"
    simulator = PaperSimulator(state_path=state)
    simulator.place_market_order(symbol="US.AAPL", side="BUY", quantity=1, price=10)
    simulator.save()
    reloaded = PaperSimulator.load(state_path=state)
    assert len(reloaded.trades) == 1
    assert reloaded.positions["US.AAPL"].quantity == 1


def test_non_finite_order_and_market_values_are_rejected(tmp_path: Path) -> None:
    state = tmp_path / "paper-sim-state.json"
    simulator = PaperSimulator(state_path=state)

    with pytest.raises(ValueError, match="quantity"):
        simulator.place_market_order(
            symbol="US.AAPL", side="BUY", quantity=float("nan"), price=10
        )
    with pytest.raises(ValueError, match="price"):
        simulator.place_market_order(
            symbol="US.AAPL", side="BUY", quantity=1, price=float("inf")
        )

    simulator.place_market_order(
        symbol="US.AAPL", side="BUY", quantity=1, price=10
    )
    with pytest.raises(ValueError, match="price for US.AAPL"):
        simulator.mark_to_market({"US.AAPL": float("nan")})


def test_save_rejects_non_finite_mutated_state_without_replacing_file(tmp_path: Path) -> None:
    state = tmp_path / "paper-sim-state.json"
    simulator = PaperSimulator(state_path=state)
    simulator.cash = float("nan")

    with pytest.raises(ValueError):
        simulator.save()

    assert not state.exists()
    assert not list(tmp_path.glob("*.tmp"))
