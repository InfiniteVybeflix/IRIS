# ─── IRIS Deployment Dockerfile ──────────────────────────────────────────
# Lightweight image with only the deps IRIS actually needs to run.
# Build: docker build -t iris-agent .
# Run:   docker run -p 5000:5000 --env-file .env iris-agent

FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Working dir
WORKDIR /app

# Copy requirements + install (slimmed to essentials)
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

# Copy IRIS code
COPY . .

# Create data dirs
RUN mkdir -p data/uploads data/iris_learnings data/iris_knowledge data/sandbox

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run IRIS
CMD ["python", "app.py"]
