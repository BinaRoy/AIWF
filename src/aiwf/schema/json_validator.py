from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from jsonschema import validate


def load_schema(repo_root: Path, schema_name: str) -> Optional[Dict[str, Any]]:
    path = repo_root / "schemas" / schema_name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_payload(payload: Dict[str, Any], schema: Optional[Dict[str, Any]]) -> None:
    if schema is None:
        return
    validate(payload, schema)
