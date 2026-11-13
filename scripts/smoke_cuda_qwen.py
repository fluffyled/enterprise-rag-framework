import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from haystack import Document

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.answer import answer
from navigator.settings import ROOT


def main():
    endpoint = "http://127.0.0.1:8080"
    deadline = time.time() + 90
    while True:
        try:
            with urllib.request.urlopen(endpoint + "/health", timeout=2) as response:
                if response.status == 200:
                    break
        except Exception:
            if time.time() >= deadline:
                raise RuntimeError("Qwen CUDA server не стал доступен за 90 секунд")
            time.sleep(1)
    os.environ["NAVIGATOR_DEBUG"] = "1"
    documents = [Document(content="Сотрудник подаёт заявку в течение пяти рабочих дней. Приказ утверждает руководитель подразделения.")]
    started = time.perf_counter()
    result = answer("В какой срок сотрудник подаёт заявку?", documents, endpoint=endpoint + "/v1/chat/completions")
    elapsed = time.perf_counter() - started
    if result.get("status") != "supported_quotes" or not result.get("answer"):
        raise RuntimeError(f"Qwen не вернула подтверждённый ответ: {result}")
    for item in result["answer"]:
        if item["quote"] not in documents[item["source"] - 1].content:
            raise RuntimeError("Нарушена дословная проверка цитаты")
    gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,memory.free,utilization.gpu", "--format=csv,noheader"], text=True).strip()
    report = {"endpoint": endpoint, "seconds": elapsed, "result": result, "literal_quotes_valid": True, "nvidia_smi": gpu}
    output = ROOT / "reports" / "retrieval_v3" / "cuda_qwen_smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
