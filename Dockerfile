# ── IRIS Dockerfile ───────────────────────────────────────────────────────────
# Builds a minimal Python 3.11 image that runs the IRIS Streamlit UI.
# Ollama must be running on the host or a sidecar container.
#
# Build:  docker build -t iris-ai .
# Run:    docker run -p 8501:8501 --env-file .env iris-ai

FROM python:3.11-slim

# System deps for pyaudio / pyttsx3
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        portaudio19-dev \
        espeak \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Streamlit config
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

CMD ["streamlit", "run", "ui/app.py"]
