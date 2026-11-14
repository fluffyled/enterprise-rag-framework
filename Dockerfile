FROM python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HAYSTACK_TELEMETRY_ENABLED=false HF_HUB_DISABLE_TELEMETRY=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-cuda.txt .
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.11.0+cpu \
    && sed '/^--extra-index-url /d; /^torch==/d' requirements-cuda.txt > /tmp/requirements.txt \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt
COPY navigator navigator
COPY answering answering
COPY ui ui
COPY configs configs
COPY demo_fixtures demo_fixtures
COPY scripts scripts
COPY app.py models.lock.json answer-model.lock.json ./
COPY .streamlit .streamlit
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
