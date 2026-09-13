# ── SMART CCTV — Cloud Run Dockerfile ──────────────────────────────────────
# Python 3.11 slim base for minimal image size
FROM python:3.11-slim

# System dependencies required by OpenCV and face recognition libraries
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1-mesa-glx \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies first (layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure data directories exist
RUN mkdir -p data/snapshots static/models

# Cloud Run uses PORT env variable (default 8080)
ENV PORT=8080
ENV HOST=0.0.0.0

# Expose port
EXPOSE 8080

# Run FastAPI via uvicorn
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 75"]
