import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json, time
from navigator.settings import ROOT
from navigator.retrieval import Retriever
from navigator.answer import answer
case_file = ROOT / "data/eval_cases.json"
if not case_file.exists():
    raise SystemExit("Создайте data/eval_cases.json с question, expected_docs, expected, gold_terms; реальные вопросы не распространяются с кодом.")
cases = json.loads(case_file.read_text(encoding="utf-8"))

r = Retriever(); results=[]
for case in cases:
    start=time.perf_counter(); docs=r.search(case["question"]); search_sec=time.perf_counter()-start
    result=answer(case["question"],docs)
    names={d.meta["name"] for d in docs}
    text=" ".join(x["quote"] for x in result["answer"]).lower()
    record=dict(case, result=result, sources=[{"id":d.id,"meta":d.meta,"text":d.content} for d in docs], retrieval_seconds=search_sec, total_seconds=time.perf_counter()-start, expected_docs_retrieved=all(n in names for n in case["expected_docs"]))
    record["gold_terms_in_answer"] = all(t in text for t in case["gold_terms"]) if case["gold_terms"] else None
    record["abstention_pass"] = result["status"] == "insufficient" if case.get("must_abstain") else None
    record["semantic_review"] = "requires_human_review"
    results.append(record)
    (ROOT/"reports/evaluation.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    print(case["id"],result["status"],"retrieved",record["expected_docs_retrieved"],"terms",record["gold_terms_in_answer"],round(record["total_seconds"],2),flush=True)
