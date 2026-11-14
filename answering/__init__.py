"""Keep this project's downloads, caches and temporary files on its own disk."""
import os
import sys
import tempfile
from pathlib import Path

_CACHE = Path(__file__).resolve().parent.parent / ".cache"
for _name, _subdir in {
    "PIP_CACHE_DIR": "pip", "HF_HOME": "huggingface",
    "HF_HUB_CACHE": "huggingface/hub", "HF_ASSETS_CACHE": "huggingface/assets",
    "HF_DATASETS_CACHE": "huggingface/datasets", "TORCH_HOME": "torch",
    "CUDA_CACHE_PATH": "cuda", "TORCH_EXTENSIONS_DIR": "torch-extensions",
    "TRITON_CACHE_DIR": "triton",
    "SENTENCE_TRANSFORMERS_HOME": "sentence-transformers", "XDG_CACHE_HOME": "xdg",
    "TEMP": "tmp", "TMP": "tmp", "TMPDIR": "tmp",
}.items():
    _path = _CACHE / _subdir
    _path.mkdir(parents=True, exist_ok=True)
    os.environ[_name] = str(_path)
tempfile.tempdir = os.environ["TEMP"]
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True
