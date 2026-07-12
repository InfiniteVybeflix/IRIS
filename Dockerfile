FROM python:3.11-slim

LABEL maintainer="Infinite Vybeflix <aevibron@gmail.com>"
LABEL version="9.0.0"
LABEL description="IRIS v9 — Infinite Reactive Intelligence System"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV IRIS_HOME=/app
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ffmpeg libsm6 libxext6 libgl1-mesa-glx \
    tesseract-ocr libtesseract-dev poppler-utils build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p \
    data/{experiences,iris_learnings,iris_knowledge,iris_self,uploads,vector_db,backups,sandbox,calendar,notes,projects,memory} \
    outputs/{images,audio,video,3d,motion,science} \
    models/{text,image,audio,video,3d,motion,robotics,science} \
    logs

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--timeout", "120", "--keep-alive", "5", "app:app"]
