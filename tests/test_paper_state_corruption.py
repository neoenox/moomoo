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
        b"\\xff",
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
