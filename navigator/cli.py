import argparse
from .settings import DATA

def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["ingest", "index", "ask"])
    p.add_argument("question", nargs="?")
    args = p.parse_args()
    if args.command == "ingest":
        from .ingest import ingest
        print("Извлечено фрагментов:", len(ingest()))
    elif args.command == "index":
        from .retrieval import build_index
        print("Проиндексировано:", build_index())
    else:
        import json
        from .retrieval import Retriever
        from .answer import answer
        docs = Retriever().search(args.question or "")
        print(json.dumps({"result": answer(args.question or "", docs), "sources": [{"meta": d.meta, "text": d.content} for d in docs]}, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
