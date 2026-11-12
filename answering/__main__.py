import argparse,json
from pathlib import Path
from .contracts import read_bundle
from .core import generate
p=argparse.ArgumentParser(description="Независимая вторая часть: ответ по результату поиска")
p.add_argument("bundle",type=Path)
p.add_argument("question")
args=p.parse_args()
if args.bundle.stat().st_size>5*1024*1024:p.error("JSON превышает 5 MiB")
try:
    fragments=read_bundle(json.loads(args.bundle.read_text(encoding="utf-8-sig")))
    result=generate(args.question,fragments)
except (ValueError,TypeError,KeyError) as exc:p.error(str(exc))
print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(2 if result["status"]=="error" else 0)
