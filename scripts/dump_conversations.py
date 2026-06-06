"""Safety backup + analysis dump of all production conversations.

Writes three files into backups/ (gitignored):
  - conversations-<ts>.jsonl  : every message row, one JSON object per line (raw backup)
  - faq-<ts>.json             : the full FAQ table (source of truth for accuracy checks)
  - rendered-<ts>/            : one .txt per conversation, human-readable transcript

Read-only against the production DB. Run: uv run --directory backend python ../scripts/dump_conversations.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / "backups"
BACKUPS.mkdir(exist_ok=True)
TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump():
    rows = db.all_message_rows()
    archive = db.all_archive_rows()
    faqs = db.list_faqs()

    jsonl_path = BACKUPS / f"conversations-{TS}.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    archive_path = BACKUPS / f"archive-{TS}.jsonl"
    with archive_path.open("w", encoding="utf-8") as f:
        for row in archive:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    faq_path = BACKUPS / f"faq-{TS}.json"
    faq_path.write_text(json.dumps(faqs, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    rendered = render(rows + archive)
    rendered_path = BACKUPS / f"rendered-{TS}.txt"
    rendered_path.write_text(rendered, encoding="utf-8")

    print(f"messages: {len(rows)} rows")
    print(f"archive:  {len(archive)} rows")
    print(f"faqs:     {len(faqs)} rows")
    print(f"wrote {jsonl_path}")
    print(f"wrote {archive_path}")
    print(f"wrote {faq_path}")
    print(f"wrote {rendered_path}")


def render(rows: list[dict]) -> str:
    """Group rows by conversation_id, ordered by first message time, as readable transcripts."""
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["conversation_id"], []).append(row)

    convos = []
    for cid, group in grouped.items():
        group.sort(key=lambda r: r["id"])
        convos.append((cid, group))
    convos.sort(key=lambda c: c[1][0]["created_at"])

    out = [f"TOTAL CONVERSATIONS: {len(convos)}\n"]
    for i, (cid, group) in enumerate(convos, 1):
        name = next((r["conversation_name"] for r in reversed(group) if r.get("conversation_name")), None)
        first_ts = group[0]["created_at"]
        out.append("=" * 100)
        out.append(f"CONVERSATION {i}/{len(convos)}  id={cid}  name={name!r}  started={first_ts}  messages={len(group)}")
        out.append("=" * 100)
        for r in group:
            tools = r.get("tool_calls")
            tool_note = f"  [tools: {tools}]" if tools else ""
            flags = []
            if r.get("needs_attention"):
                flags.append("NEEDS_ATTENTION")
            flag_note = f"  [{', '.join(flags)}]" if flags else ""
            out.append(f"\n--- {r['role'].upper()} ({r['created_at']}){tool_note}{flag_note} ---")
            out.append((r.get("content") or "").strip())
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    dump()
