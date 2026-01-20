.PHONY: install install-backend install-frontend backend frontend build test lint lint-fix clean help

# 默认目标
.DEFAULT_GOAL := help

# ==================== 安装 ====================

install: install-backend install-frontend ## 安装所有依赖

install-backend: ## 安装 Python 依赖
	cd backend && uv sync

install-frontend: ## 安装前端依赖
	cd frontend && npm install

# ==================== 开发 ====================

backend: ## 启动后端开发服务器
	cd backend && uv run v2t-web

frontend: ## 启动前端开发服务器
	cd frontend && npm run dev

# ==================== 构建 ====================

build: build-frontend ## 构建项目

build-frontend: ## 构建前端到 frontend/dist/
	cd frontend && npm run build

# ==================== 测试 ====================

test: ## 运行所有测试
	cd backend && uv run pytest

test-v: ## 运行测试 (详细输出)
	cd backend && uv run pytest -v

# ==================== Lint ====================

lint: lint-backend lint-frontend ## 运行所有 lint 检查

lint-backend: ## 运行 Python lint (ruff)
	cd backend && uv run ruff check app/ tests/

lint-frontend: ## 运行前端 lint (eslint + typecheck)
	cd frontend && npm run lint && npm run type-check

lint-fix: lint-fix-backend lint-fix-frontend ## 自动修复所有 lint 问题

lint-fix-backend: ## 自动修复 Python lint 问题
	cd backend && uv run ruff check app/ tests/ --fix

lint-fix-frontend: ## 自动修复前端 lint 问题
	cd frontend && npm run lint:fix

# ==================== 清理 ====================

clean: ## 清理构建产物和缓存
	rm -rf frontend/dist
	rm -rf backend/.pytest_cache
	rm -rf backend/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ==================== Docker ====================

docker-build: ## 构建 Docker 镜像
	docker build -t v2t:latest .

docker-up: ## 启动 Docker 容器
	docker-compose up -d

docker-down: ## 停止 Docker 容器
	docker-compose down

docker-logs: ## 查看 Docker 日志
	docker-compose logs -f

# ==================== 帮助 ====================

help: ## 显示帮助信息
	@echo "v2t - 视频转文字工具"
	@echo ""
	@echo "用法: make [目标]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
