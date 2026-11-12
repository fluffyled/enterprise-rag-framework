"""Local smoke test; private questions/answers stay under reports/."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from answering.bridge import BaselineSearch
from answering.core import generate
from answering.catalog import DATA
root=DATA.parent
search=BaselineSearch()
case_file=DATA/"answer_cases.json"
if not case_file.exists():raise SystemExit("Подготовьте локальный data/answer_cases.json с id и question")
questions=[(c["id"],c["question"]) for c in json.loads(case_file.read_text(encoding="utf-8"))]
results=[]
for tag,q in questions:
    start=time.perf_counter();fragments=search.search(q);search_seconds=time.perf_counter()-start
    r=generate(q,fragments)
    record={"case":tag,"question":q,"result":r,"search_seconds":search_seconds,"seconds":time.perf_counter()-start,"sources":[f.to_dict() for f in fragments]}
    results.append(record)
    (root/"reports/answering_real.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    print(tag,r["status"],len(r["answer"]),round(record["seconds"],2),flush=True)
