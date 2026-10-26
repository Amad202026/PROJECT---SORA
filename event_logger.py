from datetime import datetime, timezone
from pathlib import Path
import json
import time
import uuid


class EventLogger:
    def __init__(self, directory):
        self.session_id = uuid.uuid4().hex[:12]
        self.started_at = time.perf_counter()
        self.enabled = True

        directory = Path(directory)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = directory / f"session_{stamp}_{self.session_id}.jsonl"

        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.enabled = False
            print(f"Event logging unavailable: {error}")

    def write(self, event, **details):
        if not self.enabled:
            return

        record = {
            "schema_version": 1,
            "session_id": self.session_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(
                time.perf_counter() - self.started_at, 3
            ),
            "event": event,
            "details": details,
        }

        try:
            line = json.dumps(record, ensure_ascii=False, allow_nan=False)

            with self.path.open("a", encoding="utf-8") as file:
                file.write(line + "\n")

        except (OSError, TypeError, ValueError) as error:
            self.enabled = False
            print(f"Event logging stopped: {error}")