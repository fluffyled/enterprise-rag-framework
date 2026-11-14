"""Convert existing evaluate_complex_rag traces without rerunning retrieval."""
import argparse
import json
from pathlib import Path

from answering.research import freeze_documents
from haystack import Document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = json.loads(args.trace.read_text(encoding="utf-8-sig"))
    frozen = []
    for row in rows:
        documents = [Document(id=item["id"], content=item["content"], meta=item["meta"])
                     for item in row["trace"]["results"]]
        request = freeze_documents(row["question"], documents)
        frozen.append({"id": row["id"], "input": request.model_dump()})
    with args.output.open("x", encoding="utf-8") as stream:
        for row in frozen:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
