from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping, Optional


class PortfolioOutputAuditLogger:
    FIELDNAMES = [
        "timestamp_utc",
        "operation",
        "model_deployment",
        "request_json",
        "output_text",
        "output_json",
        "output_char_count",
    ]

    def __init__(self, csv_path: Optional[str], enabled: bool = True):
        self.csv_path = (csv_path or "").strip()
        self.enabled = enabled and bool(self.csv_path)

    def record(
        self,
        *,
        operation: str,
        model_deployment: str,
        request_payload: Mapping[str, Any],
        output_text: str,
        output_payload: Optional[Mapping[str, Any]] = None,
    ) -> None:
        if not self.enabled:
            return

        csv_path = os.path.abspath(self.csv_path)
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        should_write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0

        row = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "model_deployment": model_deployment,
            "request_json": json.dumps(request_payload, ensure_ascii=False, sort_keys=True),
            "output_text": output_text,
            "output_json": json.dumps(output_payload or {}, ensure_ascii=False, sort_keys=True),
            "output_char_count": len(output_text),
        }

        with open(csv_path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
            if should_write_header:
                writer.writeheader()
            writer.writerow(row)
