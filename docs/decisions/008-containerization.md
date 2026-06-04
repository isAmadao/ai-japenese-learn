# 008 · 容器化方案

- **日期**: 2026-06-04
- **状态**: 🔄 待决策

## 背景

项目目前需要本地安装 Python 3.12 + conda + Redis + Milvus Lite 等依赖。需要标准化的部署方案。

## 待决策事项

- [ ] Dockerfile 构建后端镜像（Python 3.12-slim + 依赖）
- [ ] docker-compose 编排（后端 + Redis + 前端）
- [ ] 前端 Nginx 容器化
- [ ] 生产环境 MySQL / Milvus 集群配置
- [ ] CI/CD 流水线

## 可选方案

| 方案 | 复杂度 | 适用场景 |
|------|--------|----------|
| Docker Compose | 中 | 本地开发 / 单机部署 |
| Kubernetes | 高 | 生产集群 |
| 直接部署 | 低 | 开发环境（当前） |

## 当前状态

开发阶段暂不容器化，直接使用 conda 环境 + uvicorn 运行。如有部署需求，优先使用 Docker Compose。

## 关联

- [001 · 关系型数据库选型](001-database-selection.md)
- [003 · 后端框架 & LLM 集成](003-backend-framework.md)
