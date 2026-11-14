import json
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import answering
from huggingface_hub import HfApi, snapshot_download, hf_hub_download
root = Path(__file__).resolve().parent.parent
models = root / "models"
models.mkdir(exist_ok=True)
lock_path = root / "models.lock.json"
lock = json.loads(lock_path.read_text()) if lock_path.exists() else {}
specs = {"embedding": "intfloat/multilingual-e5-small", "reranker": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "llm": "Qwen/Qwen2.5-3B-Instruct-GGUF"}
parser = argparse.ArgumentParser()
parser.add_argument("--bge", action="store_true", help="Download the frozen BGE models for Fast and Quality")
if parser.parse_args().bge:
    for role in ("bge_m3", "reranker_bge_v2_m3"):
        entry = lock[role]
        path = snapshot_download(entry["repo"], revision=entry["revision"], local_dir=models / entry["local_dir"],
                                 ignore_patterns=["onnx/*", "openvino/*", "*.h5", "*.ot", "*.msgpack"])
        print(role, path, flush=True)
    raise SystemExit(0)
for role, repo in specs.items():
    revision = lock.get(role, {}).get("revision") or HfApi().model_info(repo).sha
    lock[role] = {"repo": repo, "revision": revision}
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    if role == "llm":
        path = hf_hub_download(repo, filename="qwen2.5-3b-instruct-q4_k_m.gguf", revision=revision, local_dir=models / "llm3")
    else:
        path = snapshot_download(repo, revision=revision, local_dir=models / role, allow_patterns=["*.json", "*.safetensors", "tokenizer*", "sentencepiece*", "*.model", "modules.json", "1_Pooling/*"], ignore_patterns=["onnx/*", "openvino/*"])
    print(role, revision, path, flush=True)
