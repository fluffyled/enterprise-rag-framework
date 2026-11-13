"""Evaluation daemon: держит Retriever'ы (BGE-M3 + reranker) в памяти.

Убирает загрузку моделей (~2 минуты) между прогонами: очередные задачи
принимаются по HTTP, Retriever кэшируется по (config, index_path).
Задачи выполняются последовательно (одна GPU). LLM (llama-server) поднимается
отдельно с --parallel для конкурентной генерации.

API:
  GET  /status → {"cached": [[config, index_path], ...], "busy": bool}
  POST /eval   → тело = аргументы evaluate_complex_rag (config, index_path,
                 split, name, llm, generation_mode, parallel, endpoint)
                 ответ: {"ok": true, "metrics": {...}}
  POST /shutdown → завершить daemon
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.evaluate_complex_rag as evaluator

LOCK = threading.Lock()
BUSY = {"flag": False}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/status":
            self._send(200, {"cached": [list(key) for key in evaluator._RETRIEVER_CACHE], "busy": BUSY["flag"]})
        else:
            self._send(404, {"error": "unknown path"})

    def do_POST(self):
        if self.path == "/shutdown":
            self._send(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path != "/eval":
            self._send(404, {"error": "unknown path"})
            return
        if BUSY["flag"]:
            self._send(409, {"error": "busy"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            args = SimpleNamespace(
                config=payload.get("config", "configs/retrieval_bge_adaptive_rerank.yaml"),
                index_path=payload.get("index_path"),
                split=payload.get("split", "all"),
                name=payload["name"],
                llm=bool(payload.get("llm")),
                generation_mode=payload.get("generation_mode", "quotes"),
                parallel=int(payload.get("parallel", 4)),
                oracle=bool(payload.get("oracle")),
                endpoint=payload.get("endpoint", "http://127.0.0.1:8080/v1/chat/completions"),
            )
        except Exception as error:
            self._send(400, {"error": str(error)})
            return
        BUSY["flag"] = True
        try:
            metrics = evaluator.run(args)
            self._send(200, {"ok": True, "metrics": metrics})
        except Exception as error:
            self._send(500, {"error": str(error)})
        finally:
            BUSY["flag"] = False


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8390
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"eval daemon on 127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
