from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from moomoo_bot.orchestrator.repair import _clear_state_files
from moomoo_bot.state import StateStore


def _store_with_committed_wal_row(tmp_path: Path) -> tuple[StateStore, Path]:
    db_path = tmp_path / "paper-state.db"
    store = StateStore(db_path=db_path, execution_mode="paper")
    connection = store._connect()
    connection.execute("PRAGMA wal_autocheckpoint=0")
    connection.execute(
        """
        INSERT INTO equity_curve (
            timestamp, account_value, cash, positions_json, market_date
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ("2026-11-14T00:00:00+00:00", 1234.5, 1000.0, "{}", "2026-11-14"),
    )
    connection.commit()

    wal_path = Path(f"{db_path}-wal")
    assert wal_path.exists()
    assert wal_path.stat().st_size > 0
    return store, db_path


def test_paper_repair_backup_includes_committed_wal_frames(tmp_path: Path) -> None:
    store, db_path = _store_with_committed_wal_row(tmp_path)

    _clear_state_files(store)

    backup_path = db_path.with_suffix(".db.bak")
    with sqlite3.connect(backup_path) as backup:
        assert backup.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert backup.execute(
            "SELECT account_value FROM equity_curve"
        ).fetchone() == (1234.5,)

    with sqlite3.connect(db_path) as cleared:
        assert cleared.execute("SELECT COUNT(*) FROM equity_curve").fetchone() == (0,)


def test_backup_failure_keeps_source_database_untouched(tmp_path: Path) -> None:
    store, db_path = _store_with_committed_wal_row(tmp_path)
    backup_path = db_path.with_suffix(".db.bak")
    backup_path.mkdir()

    try:
        with pytest.raises(OSError):
            _clear_state_files(store)

        row = store._connect().execute(
            "SELECT account_value FROM equity_curve"
        ).fetchone()
        assert row["account_value"] == 1234.5
        assert list(tmp_path.glob(".paper-state.db.bak.*.tmp")) == []
    finally:
        store.close()
