"""Back up every message row to a local jsonl, as a safety net before archive work.

Run from the backend directory:

    uv run python -m scripts.backup_conversations

Writes backups/conversations-<UTC stamp>.jsonl in the project root (gitignored),
one JSON object per message row, ordered by id.
"""

import json
from datetime import datetime, timezone

from app.config import REPO_ROOT
from app.db import TABLE, get_client

PAGE = 1000


def fetch_all_rows() -> list[dict]:
    """Every row of the table, paging past PostgREST's default row cap."""
    client = get_client()
    rows: list[dict] = []
    start = 0
    while True:
        batch = (
            client.table(TABLE)
            .select("*")
            .order("id")
            .range(start, start + PAGE - 1)
            .execute()
            .data
        )
        rows.extend(batch)
        if len(batch) < PAGE:
            return rows
        start += PAGE


def main() -> None:
    rows = fetch_all_rows()
    backups = REPO_ROOT / "backups"
    backups.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backups / f"conversations-{stamp}.jsonl"
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")
    conversations = len({row["conversation_id"] for row in rows})
    print(f"Backed up {len(rows)} messages across {conversations} conversations to {path}")


if __name__ == "__main__":
    main()
