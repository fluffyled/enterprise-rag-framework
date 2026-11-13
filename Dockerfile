FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 HAYSTACK_TELEMETRY_ENABLED=False HF_HUB_DISABLE_TELEMETRY=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
COPY navigator navigator
COPY answering answering
COPY ui ui
COPY demo_fixtures demo_fixtures
COPY app.py models.lock.json ./
COPY .streamlit .streamlit
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
