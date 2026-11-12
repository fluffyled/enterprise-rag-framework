import hashlib,json,urllib.request,zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import answering  # Configure disk D before downloading.
root=Path(__file__).resolve().parent.parent
lock=json.loads((root/"answer-runtime.lock.json").read_text(encoding="utf-8"))
target=(root/lock["directory"]).resolve()
if not target.is_relative_to((root/"tools").resolve()):raise ValueError("Runtime должен находиться в tools")
target.mkdir(parents=True,exist_ok=True)
for asset in lock["archives"]:
    path=root/"tools"/asset["name"]
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=asset["sha256"]:
        urllib.request.urlretrieve(asset["url"],path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=asset["sha256"]:raise ValueError("Не совпала контрольная сумма runtime")
    with zipfile.ZipFile(path) as archive:
        if any(not (target/i.filename).resolve().is_relative_to(target) for i in archive.infolist()):raise ValueError("Небезопасный путь в архиве")
        archive.extractall(target)
    print(asset["name"],"ready")
