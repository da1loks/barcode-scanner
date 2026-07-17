FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HEADLESS=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    CAM_INDEX=0 \
    HISTORY_DB=/data/history.db \
    CALIB_PATH=/data/calibration.json

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgl1 \
    libv4l-0 \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y opencv-python \
    && pip install --no-cache-dir opencv-python-headless

COPY camera.py coords.py history.py server.py scan.py ./

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

CMD ["python", "server.py"]
