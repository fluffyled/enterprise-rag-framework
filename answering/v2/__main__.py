import argparse
import json
from pathlib import Path

from . import AnswerInputV1, VerifiedAnswerV1, generate_v2
from .pipeline import Settings


def main():
    parser = argparse.ArgumentParser(description="Generate an answer from saved evidence")
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("--schema", choices=["input", "output"])
    parser.add_argument("--endpoint")
    parser.add_argument("--extraction", choices=["map", "global"], default="map")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()
    if args.schema:
        model = AnswerInputV1 if args.schema == "input" else VerifiedAnswerV1
        print(json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2))
        return 0
    if args.input is None:
        parser.error("Specify an input JSON or --schema")
    request = AnswerInputV1.model_validate_json(args.input.read_text(encoding="utf-8-sig"))
    answer = generate_v2(request, endpoint=args.endpoint,
                         settings=Settings(extraction=args.extraction, verify=not args.no_verify))
    print(answer.model_dump_json(indent=2))
    return int(answer.status == "error")


if __name__ == "__main__":
    raise SystemExit(main())
