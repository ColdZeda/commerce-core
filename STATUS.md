# STATUS

> 更新于 2026-11-11（S6 收口）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S6 已完成**，业务闭环在本地跑通：登录 → 领券 → 下单 → 取消 / 超时关单 → 模拟支付。
代码在 `github.com/ColdZeda/commerce-core`（镜像 `gitee.com/ColdZeda/commerce-core`），
tag：`s0`、`s2`、`s3`、`s4`、`s5`、`s6`；CI 每次 push 都绿（lint + test）。

**S6 模拟支付**：

- `trade/payments.py`：HMAC-SHA256 签 `order_no|trade_no|amount|timestamp`，比较用 `compare_digest`，
  时间窗 ±300 秒（`PAY_CALLBACK_WINDOW_SECONDS`）
- `mark_order_paid` 是唯一入口：`/pay`（登录 + `ENABLE_MOCK_PAY`）与 `/payments/callback`（匿名 + HMAC）都走它
- `rules.py` 三行：`PENDING→CANCELLED`、`PENDING→CLOSED`、`PENDING→PAID`（PAID 无跨表副作用）
- 已支付幂等：`/pay` 与回调都返回 200（`X-Idempotent-Replay` / `idempotent: true`），`paid_at` 不变
- 已关闭/已取消的回调返回 409 `ORDER_NOT_PAYABLE`，签名/时间/金额各自独立报错
- 前端订单页与详情抽屉加了「模拟支付」，浏览器实测可用

**服务器**：`http://120.24.67.82:8080`，4 个容器（api/mysql/redis/nginx）healthy；
服务器上跑的仍是 **S2 镜像**，S3–S6 的代码都没部署（按 plan 在 S7 一起做）。

阶段记录：`docs/phases/phase0.md` … `phase6.md`；服务器事实与流水在仓库外
`..\ops\runbook.md` 与 `..\ops\server-log.md`。

## 下一步

**S7 部署与 CI/CD**（拆成两段：S7a 本地与 CI 不动服务器，S7b 部署与回滚要确认；计划见 `docs/phases/phase7.md`）：

- `deploy/docker-compose.prod.yml` 补 worker / beat 两个 service（同一个 api 镜像，不同命令）
- nginx 托管前端静态资源 + history fallback（现在 `/` 还是一行纯文本）
- CI 加 build + push 到 ACR（固定 sha tag）、GitHub Secrets、服务器侧部署脚本与回滚演练
- WSL2/Compose 全栈预演：uWSGI + nginx + worker + beat 跑通完整业务，不只用 runserver
- 公网验证：登录 → 领券 → 下单 → 取消/关单 → 支付，两条订单分别验证
- 部署前读 `..\ops\runbook.md`；服务器操作逐条进 `..\ops\server-log.md`

## 卡点

无。

## 未验证（不许当成已完成）

- S3–S6 代码还没上服务器：公网仍是 S2 镜像，`/api/v1/orders` 仍是 404
- 前端静态资源还没部署、没有 WSL2 全栈预演
- compose 里没有 worker/beat service，所以公网还没有自动关单
- ACR 的 CI 构建推送、GitHub Secrets、部署与回滚演练（S7）
- 公网 demo 用户的安全初始化方式（S8）

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → 当前阶段文件（`docs/phases/phase7.md` 已写好，从 S7a 开始）
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. 推 GitHub 要带本机代理 `-c http.proxy=http://127.0.0.1:10808`；推 Gitee 直连
4. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`；前端 `cd frontend && npm run dev`
   （本地栈的 api 容器占着 8000，跑 `runserver` 前先 `docker stop commerce-api`）
5. 压测：`cd backend && .venv\Scripts\python -m stocklab.bench`
6. 异步关单本地演练（Windows 上 beat 与 worker 必须分两个进程）：
   `celery -A config worker -l info --pool=solo` 与 `celery -A config beat -l info`
7. 模拟支付：dev 默认开；prod 要在 `.env` 里设 `ENABLE_MOCK_PAY=true` 才能点「支付」
