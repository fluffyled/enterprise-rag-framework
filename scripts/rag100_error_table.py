"""Per-question таблица ошибок rag100 по таксономии этапов пайплайна.

Классификация (для отвечаемых вопросов выбранного сплита):
- retrieval_miss: gold-документ отсутствует в reranked candidates;
- unit_miss: документ есть среди кандидатов, но gold source-unit нет;
- ranking_error: gold unit в кандидатах, но ранг > 6 (не вошёл в selected);
- selection_error: gold unit в кандидатах top-20, но селектор его не взял
  (для coverage-конфигов — переупорядочивание; для top_k-конфигов совпадает с ranking_error);
- ok: gold unit в selected-контексте.
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "reports" / "retrieval_experiments" / "rag100"
RAG = ROOT / "data" / "rag100"

CONFIGS = ["B0_baseline", "V2_stable", "V2_mmr", "V3F_final", "BGE_e2"]


def load(name, split):
    path = D / f"_{name}_{split}.jsonl"
    return {json.loads(line)["id"]: json.loads(line)["retrieved"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def gold_unit(g):
    typ = "page" if g["gold_location"]["type"] == "pdf_page" else "paragraph"
    return g["gold_document_id"], typ, str(g["gold_location"][typ])


def unit_positions(retr, want):
    return [i for i, r in enumerate(retr, 1) if (r["document_id"], r["unit_type"], str(r["unit_locator"])) == want]


def classify(g, candidates, selected):
    want = gold_unit(g)
    gold_docs = set(g["gold_document_ids"])
    cand_docs = {r["document_id"] for r in candidates}
    cand_pos = unit_positions(candidates, want)
    sel_pos = unit_positions(selected, want)
    if sel_pos:
        return "ok", sel_pos[0]
    if not (gold_docs & cand_docs):
        return "retrieval_miss", None
    if not cand_pos:
        return "unit_miss", None
    if cand_pos[0] <= 6:
        return "selection_error", cand_pos[0]
    return "ranking_error", cand_pos[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="test")
    parser.add_argument("--output", default=str(ROOT / "reports" / "retrieval_v3" / "08_rag100_error_table.md"))
    args = parser.parse_args()

    gold = [json.loads(line) for line in (RAG / "rag_gold_qa.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [g for g in gold if g["answerable"] and g["split"] == args.split]
    preds = {c: (load(f"{c}_candidates", args.split), load(f"{c}_selected", args.split)) for c in CONFIGS}

    lines = [f"# rag100 — таблица ошибок по вопросам ({args.split}, {len(rows)} отвечаемых)", ""]
    header = "| ID | Difficulty | " + " | ".join(CONFIGS) + " |"
    lines += [header, "|" + "---|" * (2 + len(CONFIGS))]
    counts = {c: {} for c in CONFIGS}
    for g in rows:
        cells = []
        for c in CONFIGS:
            verdict, rank = classify(g, preds[c][0].get(g["id"], []), preds[c][1].get(g["id"], []))
            counts[c][verdict] = counts[c].get(verdict, 0) + 1
            cells.append(verdict if verdict == "ok" else f"{verdict} (#{rank})")
        lines.append(f"| {g['id']} | {g['difficulty']} | " + " | ".join(cells) + " |")
    lines += ["", "## Сводка", "", "| Конфиг | " + " | ".join(["ok", "retrieval_miss", "unit_miss", "ranking_error", "selection_error"]) + " |", "|" + "---|" * 6]
    for c in CONFIGS:
        values = [counts[c].get(k, 0) for k in ("ok", "retrieval_miss", "unit_miss", "ranking_error", "selection_error")]
        lines.append(f"| {c} | " + " | ".join(str(v) for v in values) + " |")
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
