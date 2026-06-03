"""Seed the Supabase faq table from knowledge/faq.jsonl.

Maps jsonl keys to table columns: faq -> id, query -> concise (question and
answer unchanged). Idempotent: upserts by id, so re-running re-syncs the seed
rows without disturbing any rows the admin added later.

Run from the backend directory:

    uv run python -m scripts.seed_faq
"""

import json

from app.config import get_settings
from app.db import FAQ_TABLE, get_client


def main() -> None:
    path = get_settings().knowledge_dir / "faq.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [
        {"id": r["faq"], "concise": r["query"], "question": r["question"], "answer": r["answer"]}
        for r in rows
    ]
    get_client().table(FAQ_TABLE).upsert(records).execute()
    print(f"Seeded {len(records)} FAQ rows into '{FAQ_TABLE}'")


if __name__ == "__main__":
    main()
