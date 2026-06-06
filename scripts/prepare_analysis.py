"""Prepare analysis inputs from the latest backup dump.

Reads the newest conversations-*.jsonl and faq-*.json from backups/ and writes:
  - backups/chunks/chunk-NN.txt : K full conversations each (readable transcripts)
  - backups/reference.md        : knowledge base + FAQ (source of truth for accuracy)

Read-only. Run: uv run --directory backend python ../scripts/prepare_analysis.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / "backups"
KNOWLEDGE = ROOT / "knowledge"
CHUNK_SIZE = 12


def latest(pattern: str) -> Path:
    files = sorted(BACKUPS.glob(pattern))
    if not files:
        sys.exit(f"no files matching {pattern} in {BACKUPS}")
    return files[-1]


def load_conversations(jsonl_path: Path) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = {}
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        grouped.setdefault(row["conversation_id"], []).append(row)
    convos = []
    for cid, group in grouped.items():
        group.sort(key=lambda r: r["id"])
        convos.append((cid, group))
    convos.sort(key=lambda c: c[1][0]["created_at"])
    return convos


def render_convo(index: int, total: int, cid: str, group: list[dict]) -> str:
    name = next((r["conversation_name"] for r in reversed(group) if r.get("conversation_name")), None)
    out = [
        "=" * 100,
        f"CONVERSATION {index}/{total}  id={cid}  name={name!r}  started={group[0]['created_at']}  messages={len(group)}",
        "=" * 100,
    ]
    for r in group:
        tools = r.get("tool_calls")
        tool_note = f"  [tools: {tools}]" if tools else ""
        attn = "  [NEEDS_ATTENTION]" if r.get("needs_attention") else ""
        out.append(f"\n--- {r['role'].upper()} ({r['created_at']}){tool_note}{attn} ---")
        out.append((r.get("content") or "").strip())
    out.append("")
    return "\n".join(out)


def write_chunks(convos: list[tuple[str, list[dict]]]) -> int:
    chunks_dir = BACKUPS / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    for old in chunks_dir.glob("chunk-*.txt"):
        old.unlink()
    total = len(convos)
    n_chunks = (total + CHUNK_SIZE - 1) // CHUNK_SIZE
    for c in range(n_chunks):
        start = c * CHUNK_SIZE
        block = convos[start : start + CHUNK_SIZE]
        body = [f"CHUNK {c + 1}/{n_chunks}  (conversations {start + 1}..{start + len(block)} of {total})\n"]
        for j, (cid, group) in enumerate(block):
            body.append(render_convo(start + j + 1, total, cid, group))
        (chunks_dir / f"chunk-{c + 1:02d}.txt").write_text("\n".join(body), encoding="utf-8")
    return n_chunks


def write_reference(faq_path: Path) -> None:
    parts = ["# REFERENCE: Ed Donner knowledge base and FAQ (source of truth for accuracy)\n"]
    for fname in ("knowledge.md", "style.md", "rules.md", "fetch.md"):
        parts.append(f"\n\n# ===== knowledge/{fname} =====\n")
        parts.append((KNOWLEDGE / fname).read_text(encoding="utf-8"))
    parts.append("\n\n# ===== FAQ table (id / concise / question / answer) =====\n")
    faqs = json.loads(faq_path.read_text(encoding="utf-8"))
    for f in faqs:
        parts.append(f"\n## Q{f['id']}  (concise: {f['concise']})\n**Question:** {f['question']}\n\n**Answer:** {f['answer']}\n")
    (BACKUPS / "reference.md").write_text("".join(parts), encoding="utf-8")


def main():
    convos = load_conversations(latest("conversations-*.jsonl"))
    n_chunks = write_chunks(convos)
    write_reference(latest("faq-*.json"))
    print(f"conversations: {len(convos)}")
    print(f"chunks: {n_chunks} (chunk size {CHUNK_SIZE}) in {BACKUPS / 'chunks'}")
    print(f"reference: {BACKUPS / 'reference.md'}")


if __name__ == "__main__":
    main()
