from __future__ import annotations

import re
import threading
from datetime import date
from pathlib import Path

_LOCK = threading.Lock()
_MEETING_DIR_PATTERN = re.compile(r"^meeting-(\d+)$")


def next_meeting_id(base_dir: Path) -> int:
    max_id = 0
    for path in Path(base_dir).glob("*/*/meeting-*"):
        match = _MEETING_DIR_PATTERN.match(path.name)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return max_id + 1


def reserve_meeting_folder(base_dir: Path, when: date | None = None) -> Path:
    when = when or date.today()

    with _LOCK:
        candidate_id = next_meeting_id(base_dir)
        while True:
            folder = Path(base_dir) / f"{when.year:04d}" / f"{when.month:02d}" / f"meeting-{candidate_id:03d}"
            try:
                folder.mkdir(parents=True, exist_ok=False)
                return folder
            except FileExistsError:
                candidate_id += 1
