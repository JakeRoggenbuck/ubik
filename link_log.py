from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


LINK_LOG_PATH = Path("link_requests.log")


def record(user_id: int, username: str, url: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{timestamp} | {user_id} | {username} | {url}\n"
    with LINK_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line)


def read_log(limit: int = 50) -> str:
    if not LINK_LOG_PATH.exists():
        return "No link requests logged yet."
    lines = LINK_LOG_PATH.read_text(encoding="utf-8").splitlines()
    if not lines:
        return "No link requests logged yet."
    shown = lines[-limit:]
    return "```\n" + "\n".join(shown) + "\n```"
