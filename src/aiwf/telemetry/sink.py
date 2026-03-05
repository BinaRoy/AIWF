from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

@dataclass
class TelemetrySink:
    file_path: Path

    def emit(self, event_type: str, payload: Dict[str, Any], run_id: Optional[str] = None) -> None:
        obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "run_id": run_id,
            "payload": payload,
        }
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
