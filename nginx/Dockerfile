# ==============================================================
#  nginx/Dockerfile — AI 日本語学習
#  Multi-stage: build frontend, serve via nginx
# ==============================================================

# ── Stage 1: Build Vue frontend ─────────────────────────────
FROM docker.m.daocloud.io/library/node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install

COPY frontend/ .
RUN npx vite build

# ── Stage 2: Nginx ──────────────────────────────────────────
FROM docker.m.daocloud.io/library/nginx:alpine

# 删除默认配置
RUN rm -f /etc/nginx/conf.d/default.conf

# 复制自定义配置
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建好的前端
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:80/ || exit 1
