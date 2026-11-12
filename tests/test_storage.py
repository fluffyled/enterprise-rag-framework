"""Verify project caches and temporary files cannot fall back to the system disk."""
import json
import subprocess
import sys
from pathlib import Path


def test_storage_overrides_old_cache_paths():
    root = Path(__file__).resolve().parent.parent
    code = """
import json, os, tempfile
from pathlib import Path
for name in ('HF_HOME', 'HF_HUB_CACHE', 'TORCH_HOME', 'PIP_CACHE_DIR', 'TEMP', 'TMP'):
    os.environ[name] = 'C:/must-not-be-created'
import answering
from huggingface_hub import constants
root = Path(answering.__file__).resolve().parent.parent / '.cache'
for name in ('HF_HOME', 'HF_HUB_CACHE', 'HF_DATASETS_CACHE', 'HF_ASSETS_CACHE',
             'TORCH_HOME', 'PIP_CACHE_DIR', 'SENTENCE_TRANSFORMERS_HOME', 'TEMP', 'TMP', 'TMPDIR'):
    assert Path(os.environ[name]).is_relative_to(root), name
assert Path(constants.HF_HUB_CACHE).is_relative_to(root)
with tempfile.TemporaryDirectory() as directory:
    assert Path(directory).is_relative_to(root)
    (Path(directory) / 'check.txt').write_text('disk check')
print(json.dumps({'cache': str(root), 'temp': tempfile.gettempdir()}))
"""
    result = subprocess.run([sys.executable, '-B', '-c', code], cwd=root,
                            check=True, capture_output=True, text=True)
    assert Path(json.loads(result.stdout)['cache']) == root / '.cache'
