# Multi-stage build: compile dependencies, then minimal runtime
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system build dependencies (including portaudio for PyAudio)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    portaudio19-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ============================================================

# Runtime stage: minimal image with only what's needed
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (portaudio for audio, alsa-utils for aplay fallback)
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    alsa-utils \
    sox \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /root/.local /root/.local

# Set PATH to use local pip installs
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code
COPY . .

# Health check: verify main.py is present and readable
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD test -f /app/main.py && python -m py_compile main.py || exit 1

# Default: run the voice agent
CMD ["python", "main.py"]
