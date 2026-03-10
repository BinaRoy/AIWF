from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from aiwf.storage.ai_workspace import AIWorkspace


def _copy_schemas(repo_root: Path) -> None:
    src_schemas = Path(__file__).resolve().parents[1] / "schemas"
    shutil.copytree(src_schemas, repo_root / "schemas")


def test_read_risk_register_creates_default_registry(tmp_path: Path) -> None:
    from aiwf.runtime.risk_view import read_risk_register, waiver_counts

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    payload = read_risk_register(ws, tmp_path, create=True)

    assert payload["version"] == 1
    assert payload["risks"] == []
    assert waiver_counts(payload) == {"open": 0, "active_waivers": 0, "expired_waivers": 0}
    assert (tmp_path / ".ai" / "risk_register.json").exists()


def test_apply_risk_waiver_creates_open_risk_with_waiver(tmp_path: Path) -> None:
    from aiwf.runtime.risk_view import apply_risk_waiver, default_risk_register, waiver_counts

    now = datetime(2026, 3, 10, tzinfo=timezone.utc)
    payload = default_risk_register(now=now)

    out = apply_risk_waiver(
        payload,
        risk_id="RISK-1",
        reason="temporary exception",
        expires_at="2099-01-01",
        approved_by="reviewer",
        now=now,
    )

    risk = out["risks"][0]
    assert risk["id"] == "RISK-1"
    assert risk["status"] == "open"
    assert risk["waiver"]["approved_by"] == "reviewer"
    assert waiver_counts(out, now=now) == {"open": 1, "active_waivers": 1, "expired_waivers": 0}


def test_risk_snapshot_reports_presence_and_counts(tmp_path: Path) -> None:
    from aiwf.runtime.risk_view import apply_risk_waiver, default_risk_register, risk_snapshot, write_risk_register

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    assert risk_snapshot(ws, tmp_path)["present"] is False

    payload = default_risk_register(now=datetime(2026, 3, 10, tzinfo=timezone.utc))
    payload = apply_risk_waiver(
        payload,
        risk_id="RISK-1",
        reason="temporary exception",
        expires_at="2099-01-01",
        now=datetime(2026, 3, 10, tzinfo=timezone.utc),
    )
    write_risk_register(ws, payload)

    out = risk_snapshot(ws, tmp_path)

    assert out["present"] is True
    assert out["counts"] == {"open": 1, "active_waivers": 1, "expired_waivers": 0}
