# Docling-UI backend + UI
FROM python:3.11-slim

WORKDIR /app

# 1. System deps (rarely change; cache often)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libxcb1 \
    libxcb-xfixes0 \
    libxcb-shm0 \
    libxcb-render0 \
    libxcb-shape0 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Backend deps only (re-run only when requirements change)
COPY backend/requirements.txt backend/pyproject.toml backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# 3. Docling (heavy; re-run only when step 2 changes)
RUN pip install --no-cache-dir docling --extra-index-url https://download.pytorch.org/whl/cpu

# 4. Backend code (code-only changes skip docling reinstall)
COPY backend/src/ backend/src/
RUN pip install --no-cache-dir -e backend/

# 5. UI (only this layer re-runs when only ui/ changes)
COPY ui/ ui/
RUN pip install --no-cache-dir streamlit requests

# Data dirs
RUN mkdir -p /app/data/uploads /app/data/outputs /app/data/examples

# Entrypoint: start backend, wait for it, then Streamlit (avoids "connection refused" on first load)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=/app/backend/src
ENV DATA_ROOT=/app/data
ENV BACKEND_URL=http://127.0.0.1:8000

EXPOSE 8000 8501

ENTRYPOINT ["/entrypoint.sh"]
