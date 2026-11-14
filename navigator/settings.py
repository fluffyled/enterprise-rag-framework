import os
from pathlib import Path
os.environ.setdefault("HAYSTACK_TELEMETRY_ENABLED", "False")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("DO_NOT_TRACK", "1")
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MODELS = ROOT / "models"
INDEX = Path(os.environ["NAVIGATOR_INDEX"]) if os.environ.get("NAVIGATOR_INDEX") else DATA / "index.json"
CONFIG = os.environ.get("NAVIGATOR_CONFIG") or str(ROOT / "configs" / "retrieval_stable.yaml")
