.PHONY: install install-backend install-frontend backend worker frontend build build-frontend test test-v lint lint-backend lint-frontend lint-fix lint-fix-backend lint-fix-frontend clean docker-build docker-up docker-down docker-logs docker-deploy help

# 默认目标
.DEFAULT_GOAL := help

# 本地配置（可选，不提交到 git）
-include Makefile.local

# 部署目录（可在 Makefile.local 中覆盖）
DEPLOY_DIR ?=

# ==================== 安装 ====================

install: install-backend install-frontend ## 安装所有依赖

install-backend: ## 安装 Python 依赖
	cd backend && uv sync

install-frontend: ## 安装前端依赖（pnpm workspace）
	pnpm install

# ==================== 开发 ====================

backend: ## 启动后端开发服务器
	cd backend && uv run v2t-web

worker: ## 启动 arq worker
	cd backend && uv run arq app.worker.WorkerSettings

frontend: ## 启动前端开发服务器
	pnpm --filter @v2t/web dev

# ==================== 构建 ====================

build: build-frontend ## 构建项目

build-frontend: ## 构建前端
ifeq ($(DEPLOY_DIR),)
	pnpm --filter @v2t/web build
else
	@echo "构建到 $(DEPLOY_DIR)..."
	pnpm --filter @v2t/web build -- --outDir $(DEPLOY_DIR) --emptyOutDir
endif

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
	pnpm --filter @v2t/web lint && pnpm --filter @v2t/web type-check

lint-fix: lint-fix-backend lint-fix-frontend ## 自动修复所有 lint 问题

lint-fix-backend: ## 自动修复 Python lint 问题
	cd backend && uv run ruff check app/ tests/ --fix

lint-fix-frontend: ## 自动修复前端 lint 问题
	pnpm --filter @v2t/web lint:fix

# ==================== 清理 ====================

clean: ## 清理构建产物和缓存
	rm -rf apps/web/dist
	rm -rf backend/.pytest_cache
	rm -rf backend/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ==================== Docker ====================

docker-build: ## 构建全部 Docker 镜像（web/worker/nginx，前端 dist 在 nginx 镜像 multi-stage 内构建）
	docker compose build

docker-up: ## 启动所有服务（不重建镜像）
	docker compose up -d

docker-down: ## 停止所有服务
	docker compose down

docker-logs: ## 查看服务日志
	docker compose logs -f

docker-deploy: docker-build docker-up ## 一键部署：构建全部镜像 + 拉起服务（改前端/后端后用这条）

# ==================== 帮助 ====================

help: ## 显示帮助信息
	@echo "v2t - 视频转文字工具"
	@echo ""
	@echo "用法: make [目标]"
	@echo ""
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
