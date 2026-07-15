# ==============================================================
#  Dockerfile — AI 日本語学習
#  Multi-stage: build frontend, then bundle with Python backend
#  Search: BM25 via ES (fast, no ML deps).
#  Vector search: available when running locally with
#  ``sentence-transformers`` or ``fastembed`` installed.
# ==============================================================

# ── Stage 1: Build Vue frontend ─────────────────────────────
FROM docker.m.daocloud.io/library/node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install

COPY frontend/ .
RUN npx vite build

# ── Stage 2: Python runtime ─────────────────────────────────
FROM docker.m.daocloud.io/library/python:3.13-slim

WORKDIR /app

# Install Python dependencies.
# Strategy: pre-install CPU-only torch FIRST so easyocr doesn't pull
# in the full CUDA stack (~2GB nvidia-* packages that are never used).
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt \
    && python -c "import subprocess; r=subprocess.run(['pip','list','--format=freeze'],capture_output=True,text=True); cuda=[l.split('==')[0] for l in r.stdout.splitlines() if any(k in l.lower() for k in ['nvidia','cuda-toolkit','triton'])]; [subprocess.run(['pip','uninstall','-y',p]) for p in cuda]"

# Copy backend source
COPY backend/ .

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Create data directory
RUN mkdir -p /app/data

VOLUME ["/app/data"]

ENV FRONTEND_DIST=/app/frontend/dist
ENV USE_SQLITE=true
ENV SQLITE_PATH=/app/data/app.db
ENV HOST=0.0.0.0
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
