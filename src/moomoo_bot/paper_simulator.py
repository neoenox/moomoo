"""Local paper trading simulator.

Purpose: Broker-independent paper account simulator with local persistence.
Related: ui/paper_studio.py.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import logging
import math
import os
from pathlib import Path
import tempfile

from moomoo_bot.row_utils import utc_now_iso

logger = logging.getLogger(__name__)


_DEFAULT_SIM_DB = Path.home() / ".moomoo_bot" / "paper-sim-state.json"


def _finite_float(value: object, field: str) -> float:
    """Convert a persisted or external numeric value, rejecting NaN and infinity."""
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


@dataclass
class SimPosition:
    symbol: str
    quantity: float
    avg_cost: float


@dataclass
class SimTrade:
    trade_id: int
    timestamp: str
    symbol: str
    side: str
    quantity: float
    price: float
    notional: float
    realized_pnl: float


@dataclass
class SimSnapshot:
    timestamp: str
    cash: float
    market_value: float
    equity: float
    unrealized_pnl: float
    realized_pnl: float


class PaperStateCorruptError(RuntimeError):
    """Existing simulator state cannot be safely loaded; do not overwrite it."""


class PaperSimulator:
    def __init__(
        self,
        state_path: Path | None = None,
        initial_cash: float = 100_000.0,
    ) -> None:
        self.state_path = state_path or _DEFAULT_SIM_DB
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        self.cash: float = _finite_float(initial_cash, "initial_cash")
        self.realized_pnl: float = 0.0
        self.positions: dict[str, SimPosition] = {}
        self.trades: list[SimTrade] = []
        self.equity_curve: list[SimSnapshot] = []

    @classmethod
    def load(
        cls,
        state_path: Path | None = None,
        initial_cash: float = 100_000.0,
    ) -> "PaperSimulator":
        simulator = cls(state_path=state_path, initial_cash=initial_cash)
        if not simulator.state_path.exists():
            return simulator

        try:
            data = json.loads(simulator.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeError) as exc:
            raise PaperStateCorruptError(
                f"Cannot load paper simulator state from {simulator.state_path}; "
                "existing data was left untouched."
            ) from exc

        required = {"cash", "positions", "trades", "equity_curve"}
        if not isinstance(data, dict) or not required.issubset(data):
            raise PaperStateCorruptError(
                f"Invalid paper simulator state schema in {simulator.state_path}; "
                "existing data was left untouched."
            )

        try:
            simulator.cash = _finite_float(data.get("cash", initial_cash), "cash")
            simulator.realized_pnl = _finite_float(
                data.get("realized_pnl", 0.0), "realized_pnl"
            )

            simulator.positions = {
                symbol: SimPosition(
                    symbol=symbol,
                    quantity=_finite_float(
                        payload.get("quantity", 0.0), "position.quantity"
                    ),
                    avg_cost=_finite_float(
                        payload.get("avg_cost", 0.0), "position.avg_cost"
                    ),
                )
                for symbol, payload in data.get("positions", {}).items()
            }
            simulator.trades = [
                SimTrade(
                    trade_id=int(payload["trade_id"]),
                    timestamp=str(payload["timestamp"]),
                    symbol=str(payload["symbol"]),
                    side=str(payload["side"]),
                    quantity=_finite_float(payload["quantity"], "trade.quantity"),
                    price=_finite_float(payload["price"], "trade.price"),
                    notional=_finite_float(payload["notional"], "trade.notional"),
                    realized_pnl=_finite_float(
                        payload.get("realized_pnl", 0.0), "trade.realized_pnl"
                    ),
                )
                for payload in data.get("trades", [])
            ]
            simulator.equity_curve = [
                SimSnapshot(
                    timestamp=str(payload["timestamp"]),
                    cash=_finite_float(payload["cash"], "snapshot.cash"),
                    market_value=_finite_float(
                        payload["market_value"], "snapshot.market_value"
                    ),
                    equity=_finite_float(payload["equity"], "snapshot.equity"),
                    unrealized_pnl=_finite_float(
                        payload["unrealized_pnl"], "snapshot.unrealized_pnl"
                    ),
                    realized_pnl=_finite_float(
                        payload.get("realized_pnl", 0.0), "snapshot.realized_pnl"
                    ),
                )
                for payload in data.get("equity_curve", [])
            ]
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            raise PaperStateCorruptError(
                f"Invalid paper simulator state values in {simulator.state_path}; "
                "existing data was left untouched."
            ) from exc
        return simulator

    def save(self) -> None:
        payload = {
            "cash": _finite_float(self.cash, "cash"),
            "realized_pnl": _finite_float(self.realized_pnl, "realized_pnl"),
            "positions": {
                symbol: {
                    "quantity": _finite_float(position.quantity, "position.quantity"),
                    "avg_cost": _finite_float(position.avg_cost, "position.avg_cost"),
                }
                for symbol, position in self.positions.items()
                if _finite_float(position.quantity, "position.quantity") > 0.0
            },
            "trades": [asdict(trade) for trade in self.trades],
            "equity_curve": [asdict(snapshot) for snapshot in self.equity_curve],
        }
        # A unique same-directory temporary file avoids collisions between writers.
        # The live state is replaced only after the complete new state is durable.
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.state_path.parent,
                prefix=f".{self.state_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as output:
                tmp_path = Path(output.name)
                json.dump(payload, output, ensure_ascii=True, indent=2, allow_nan=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(tmp_path, self.state_path)
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    def reset(self, initial_cash: float = 100_000.0) -> None:
        self.cash = _finite_float(initial_cash, "initial_cash")
        self.realized_pnl = 0.0
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.save()

    def place_market_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> SimTrade:
        normalized_symbol = str(symbol).strip().upper()
        normalized_side = str(side).strip().upper()
        qty = _finite_float(quantity, "quantity")
        px = _finite_float(price, "price")

        if normalized_side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        if qty <= 0.0:
            raise ValueError("quantity must be positive")
        if px <= 0.0:
            raise ValueError("price must be positive")

        notional = _finite_float(qty * px, "notional")
        realized = 0.0

        current = self.positions.get(normalized_symbol)
        if current is None:
            current = SimPosition(symbol=normalized_symbol, quantity=0.0, avg_cost=0.0)

        if normalized_side == "BUY":
            if notional > self.cash:
                raise ValueError("insufficient cash")
            new_qty = _finite_float(current.quantity + qty, "position.quantity")
            new_avg_cost = _finite_float(
                ((current.avg_cost * current.quantity) + notional) / new_qty,
                "position.avg_cost",
            )
            current.quantity = new_qty
            current.avg_cost = new_avg_cost
            self.cash = _finite_float(self.cash - notional, "cash")
        else:
            if qty > current.quantity:
                raise ValueError("insufficient position")
            realized = _finite_float((px - current.avg_cost) * qty, "realized_pnl")
            current.quantity -= qty
            self.cash = _finite_float(self.cash + notional, "cash")
            self.realized_pnl = _finite_float(
                self.realized_pnl + realized, "realized_pnl"
            )

        if current.quantity <= 0.0:
            self.positions.pop(normalized_symbol, None)
        else:
            self.positions[normalized_symbol] = current

        trade = SimTrade(
            trade_id=len(self.trades) + 1,
            timestamp=utc_now_iso(),
            symbol=normalized_symbol,
            side=normalized_side,
            quantity=qty,
            price=px,
            notional=notional,
            realized_pnl=realized,
        )
        self.trades.append(trade)
        return trade

    def mark_to_market(self, prices: dict[str, float]) -> SimSnapshot:
        market_value = 0.0
        unrealized_pnl = 0.0
        for symbol, position in self.positions.items():
            price = _finite_float(
                prices.get(symbol, position.avg_cost), f"price for {symbol}"
            )
            market_value = _finite_float(
                market_value + position.quantity * price, "market_value"
            )
            unrealized_pnl = _finite_float(
                unrealized_pnl + (price - position.avg_cost) * position.quantity,
                "unrealized_pnl",
            )

        equity = _finite_float(self.cash + market_value, "equity")
        snapshot = SimSnapshot(
            timestamp=utc_now_iso(),
            cash=self.cash,
            market_value=market_value,
            equity=equity,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=_finite_float(self.realized_pnl, "realized_pnl"),
        )
        self.equity_curve.append(snapshot)
        return snapshot
