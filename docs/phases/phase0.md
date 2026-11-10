# phase0 — S0 基线

> 阶段号与 `docs/plan.md` §11 的 S0 对应。阶段结束封口，不再追加；新内容进 phase1。

## 目标

把"环境、依赖、镜像、CI、部署形态"这些最容易拖到最后的问题，在第一阶段证明可行。**本阶段不写业务代码。**

## 开工动作

1. 读 `AGENTS.md` → `STATUS.md` → `docs/plan.md` §0、§2、§10 → 本文件。
2. 建 todo，向用户复述：本阶段范围、将要改的目录、验收方式。
3. 用官方生成器建骨架（`django-admin startproject` / `npm create vite`），**不 clone 完整 MVP**。
4. 每完成一项，把证据（命令 + 输出摘要 + 日期）追加到本文件"证据"区。

## 任务

- [x] 后端骨架（Django 5 + DRF），settings 按环境分层，`.env.example`
- [x] 前端骨架（Vite + Vue 3 + Router + Pinia + axios + Element Plus）
- [x] `deploy/`：docker-compose（mysql + redis，固定 tag 不用浮动 `mysql:8`）
- [x] `/health`：db + redis 检查，失败返回 503
- [x] Windows 侧 PyMySQL 垫片 + `cryptography`，实测能连 MySQL 8
- [x] 依赖锁定：版本写死，`pip freeze` 与 lock 一致
- [x] ruff 配置；`scripts/check_comments.py` 接入 CI
- [x] 冒烟测试：health、一条注释检查
- [x] Linux 镜像内 uWSGI 实际启动并访问 Django（**不是 runserver**）
- [x] CI 初线：lint + test（不含 build / push / deploy）
- [x] 首个 commit 与 tag 约定

## 门槛（全部满足才算完成）

- [x] `docker compose up` 后 `/api/v1/health` 返回 200，`db` 与 `redis` 均为 `true`
- [x] Windows 本机能连上容器里的 MySQL 8（插入一条记录并读回）
- [x] Linux 镜像里 uWSGI 起得来，能返回 Django 响应
- [x] CI 绿（lint + test）—— 本地等价执行全绿；Actions 实跑待用户建远程仓库后补，见 E7
- [x] 依赖版本锁定且可复现（换目录重装一次仍能跑）
- [x] 没有任何业务代码抢跑

## 证据

### E1 工具链（2026-11-10，Windows 开发机）

```text
Windows 11 家庭版 10.0.26200 / 13.9GB RAM / 12 逻辑核
Python 3.12.8（py -3.12 → backend/.venv），pip 25.3
Docker 29.3.1，Docker Compose v5.1.1，Docker Desktop linux 引擎 7.1GB / 12 CPU
Node v24.22.2，npm 11.19.1
```

Docker Hub 在本机直连不通（`registry-1.docker.io:443` 连接超时），PyPI 与 npm 正常。改为从
`docker.m.daocloud.io` 拉取后 retag 成官方镜像名，`deploy/docker-compose.yml` 里仍写官方名，
本机与 CI 都用同一份 compose。**这是本机网络限制，不是项目设计。**

### E2 镜像与版本（钉死，不用浮动 tag）

```text
mysql:8.0.43              sha256:3e646bcda0d9448ffa3d2024eef04e1bca95528ec19b9e8b76749da9d97d4a10
redis:7.4.2               sha256:fbdbaea47b9ae4ecc2082ecdb4e1cea81e32176ffb1dcf643d422ad07427e5d9
python:3.12-slim-bookworm sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
commerce-core-api:s0      约 323 MB（含 python:3.12-slim 基础层，docker images 统计）
uwsgi==2.0.31  mysqlclient==2.3.0
```

首次本机构建约 35 分钟，时间几乎都花在 `deb.debian.org` 下载 77.8MB apt 包（实测约 80–120KB/s）。
CI 上的耗时**未测**，不写估计值。

### E3 骨架（官方生成器，未 clone MVP）

```text
backend/  django-admin startproject config .   → Django 5.2.19，DRF 3.16.1
frontend/ npm create vite@latest --template vue → create-vite 9.3.4，Vite 8.3.7，Vue 3.5.x
          vue-router 4.6.4、pinia 4.1.0、axios 1.21.1、element-plus 2.14.8、eslint 10.14
```

settings 分 `base/dev/test/prod`；`manage.py` 默认 dev，`wsgi.py` 默认 prod。

### E4 门槛 1：compose up 后 `/api/v1/health` 为 200 且 db/redis 均 true

```text
docker compose -f deploy/docker-compose.yml --env-file .env down     # 保留卷
docker compose -f deploy/docker-compose.yml --env-file .env up -d
→ commerce-api / commerce-mysql / commerce-redis 全部 healthy（8s）

curl http://127.0.0.1:8000/api/v1/health
→ status=200  {"status": "ok", "db": true, "redis": true}
```

C2 的失败分支用真实故障验证（只停本项目 redis，随后启回）：

```text
docker compose ... stop redis  → status=503  {"status": "error", "db": true, "redis": false}
docker compose ... start redis → status=200  {"status": "ok", "db": true, "redis": true}
```

MySQL 运行参数与 C3 对齐：

```text
VERSION()=8.0.43  innodb_lock_wait_timeout=10  innodb_buffer_pool_size=128MB
max_connections=50  performance_schema=0  character_set_server=utf8mb4
collation_server=utf8mb4_0900_ai_ci
```

### E5 门槛 2：Windows 本机连容器 MySQL 8 并插入读回

`backend/scripts/db_smoke.py` 走 Django 连接（Windows 下由 `config/__init__.py` 装上 PyMySQL 垫片），
建临时表 → 插入 → 读回 → 删表（临时表不落库，不污染 schema、不需要迁移）：

```text
python scripts/db_smoke.py
server=8.0.43 charset=utf8mb4 isolation=READ-COMMITTED
roundtrip=windows-pymysql
```

驱动版本：PyMySQL 1.1.3 + cryptography 46.0.7。
隔离级别是**显式配置**的 `read committed`（Django 5.2 对 MySQL 的默认值），原因见 `docs/plan-changes.md` D-002。

### E6 门槛 3：Linux 镜像里 uWSGI 实际启动并返回 Django 响应

```text
docker compose ... up -d api        → commerce-api healthy
docker exec commerce-api uwsgi --version   → 2.0.31
docker exec commerce-api python -c "import MySQLdb; print(MySQLdb.version_info)" → (2, 3, 0, 'final', 0)
docker logs commerce-api：
  Python version: 3.12.16 (main, Nov  5 2026, 07:58:44) [GCC 12.2.0]
  WSGI app 0 (mountpoint='') ready in 1 seconds ...
  spawned uWSGI master process (pid: 1)
  spawned uWSGI worker 1 (pid: 7, cores: 2)
  spawned uWSGI worker 2 (pid: 9, cores: 2)
docker top commerce-api  → 3 个 uwsgi 进程，user 10001（非 root）
curl http://127.0.0.1:8000/api/v1/health → 200 {"status":"ok","db":true,"redis":true}
```

用的是 `uwsgi --ini /app/deploy/uwsgi.ini`，**不是 runserver**；`harakiri=30` 与 C3 链一致。

### E7 门槛 4：CI 绿 —— 本地等价执行全绿，Actions 实跑待仓库

工作流 `.github/workflows/ci.yml` 只有两个 job：`lint`（ruff、`check_comments.py`、`check_lock.py`、eslint）
与 `test`（pytest + MySQL/Redis service），不含 build / push / deploy（C7）。

本地逐条执行同一批命令：

```text
ruff check .                → All checks passed!
ruff format --check .       → 17 files already formatted
python scripts/check_lock.py        → lock=19 installed=19，一致
python scripts/check_comments.py backend → 注释行 5 / 代码行 248，占比 2.0%，OK
cd frontend && npm run lint → 0 error 0 warning
cd backend && pytest -q     → 3 passed
```

**未完成部分**：远程仓库还没建，`on: push` 尚未真正触发过。建仓并 push 后需补一条真实 Actions 运行记录，
在那之前"CI 绿"只能算本地等价证据，`STATUS.md` 的未验证区保留这一条。

### E8 门槛 5：依赖锁定可复现

`requirements.txt`（运行时）、`requirements-dev.txt`（+测试工具）、`requirements-prod.txt`（Linux 专属
mysqlclient/uWSGI）全部 `==` 钉死，含传递依赖。在 `backend/.scratch/repro-venv` 新建干净 venv：

```text
py -3.12 -m venv .scratch/repro-venv
pip install -r backend/requirements-dev.txt     → 成功
python scripts/check_lock.py <repro-venv>/python → lock=19 installed=19，一致
<repro-venv>/python -m pytest -q                → 3 passed
```

主 venv 同样 `lock=19 installed=19`。`backend/scripts/check_lock.py` 已接进 CI，换机器重装若解析到
不同版本会直接红。带环境标记的条目按当前解释器求值（`colorama` 只在 Windows 装），模拟 Linux 求值时
lock 为 18 条、不含 colorama，两侧都不会误报。

### E9 门槛 6：没有业务代码抢跑

本阶段只新增：settings 分层、`health` 探针（db/redis 各一次探测）、`tests/test_health.py`、
`scripts/db_smoke.py`、`scripts/check_lock.py`、compose/Dockerfile/uWSGI、前端一个 `/` 自检页。
没有商品/券/订单模型，没有迁移文件（除 Django 自带的），没有 14 个业务接口中的任何一个。

### E10 其他实测（本机 Docker Desktop，不代表服务器预算）

```text
docker stats --no-stream:  mysql 127.3MiB / redis 3.5MiB / api 98.3MiB
```

plan §10.3 的内存预算是**服务器**目标值，这里只是本机开发环境读数，两者不混写；服务器实测在 S2 做。

### E11 commit 与 tag 约定

- commit 前缀：`feat` / `fix` / `chore` / `docs` / `test`，冒号后写一句中文结论。
- 每个阶段收口打 annotated tag `sN`（S0 → `s0`），tag 指向收口提交；发布点另用 `vX.Y.Z`。
- 首个提交是骨架（`a5d1b10`），S0 收口提交由 `git tag s0` 标记，不在文档里写死 hash。
