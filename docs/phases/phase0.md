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

- [ ] 后端骨架（Django 5 + DRF），settings 按环境分层，`.env.example`
- [ ] 前端骨架（Vite + Vue 3 + Router + Pinia + axios + Element Plus）
- [ ] `deploy/`：docker-compose（mysql + redis，固定 tag 不用浮动 `mysql:8`）
- [ ] `/health`：db + redis 检查，失败返回 503
- [ ] Windows 侧 PyMySQL 垫片 + `cryptography`，实测能连 MySQL 8
- [ ] 依赖锁定：版本写死，`pip freeze` 与 lock 一致
- [ ] ruff 配置；`scripts/check_comments.py` 接入 CI
- [ ] 冒烟测试：health、一条注释检查
- [ ] Linux 镜像内 uWSGI 实际启动并访问 Django（**不是 runserver**）
- [ ] CI 初线：lint + test（不含 build / push / deploy）
- [ ] 首个 commit 与 tag 约定

## 门槛（全部满足才算完成）

- [ ] `docker compose up` 后 `/api/v1/health` 返回 200，`db` 与 `redis` 均为 `true`
- [ ] Windows 本机能连上容器里的 MySQL 8（插入一条记录并读回）
- [ ] Linux 镜像里 uWSGI 起得来，能返回 Django 响应
- [ ] CI 绿（lint + test）
- [ ] 依赖版本锁定且可复现（换目录重装一次仍能跑）
- [ ] 没有任何业务代码抢跑

## 证据

（命令 + 输出摘要 + 日期，逐条追加）
