import hashlib,json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import answering  # Configure disk D before downloading.
from huggingface_hub import hf_hub_download
root=Path(__file__).resolve().parent.parent
lock=json.loads((root/"answer-model.lock.json").read_text(encoding="utf-8"))
path=Path(hf_hub_download(lock["repo"],lock["filename"],revision=lock["revision"],local_dir=root/lock["local_dir"]))
with path.open("rb") as stream:
    if hashlib.file_digest(stream,"sha256").hexdigest()!=lock["sha256"]:raise ValueError("Не совпала контрольная сумма модели")
print(path)
