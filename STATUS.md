# STATUS

> 更新于 2026-11-11（S5 收口）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S5 已完成**，代码在 `github.com/ColdZeda/commerce-core`（镜像 `gitee.com/ColdZeda/commerce-core`），
tag：`s0`、`s2`、`s3`、`s4`、`s5`；CI 每次 push 都绿（lint + test）。

**S5 异步关单**已跑通并演练过：

- `config/celery.py` + `CELERY_*` 设置：broker 复用 Redis，不配 result backend，`acks_late`、`prefetch=1`、
  软/硬超时 50/60、`visibility_timeout=120`（= 2 倍硬超时，理由写在 phase5）
- `trade/tasks.py`：`close_expired_orders(batch=100)` 只做批量与计数；beat 每 60 秒投递
- `trade/services.py`：`_apply_transition` 是唯一的迁移执行器，`cancel_order` 与 `close_order` 共用；
  `rules.py` 现在有 `PENDING→CANCELLED` 与 `PENDING→CLOSED` 两行
- 实测：worker + beat 把到期订单关成 CLOSED、库存与券回来；停 worker 后任务排队、恢复后补做；
  停 Redis 后 worker 指数退避重连、beat 丢一拍、恢复后下一拍把停机期间的到期单关掉
- 反例：先查状态再回补的写法在并发下双回补（库存 8 → 12），共享 service 只回补一次

**服务器**：`http://120.24.67.82:8080`，4 个容器（api/mysql/redis/nginx）healthy；
服务器上跑的仍是 **S2 镜像**，S3/S4/S5 的新代码都没部署（按 plan 在 S7 一起做）。

阶段记录：`docs/phases/phase0.md` … `phase5.md`；服务器事实与流水在仓库外
`..\ops\runbook.md` 与 `..\ops\server-log.md`。

## 下一步

**S6 模拟支付**。第一步先写 `docs/phases/phase6.md`（计划 + 门槛），再实施：

- `POST /orders/{order_no}/pay`（mock，`ENABLE_MOCK_PAY` 开关）与 `POST /payments/callback`（匿名 + HMAC）
- 两者共用 `mark_order_paid(order_no, amount, trade_no, ...)`，只做 `PENDING→PAID` 的条件更新
- `rules.py` 加 `PENDING→PAID` 一行（副作用只有 `paid_at`，不回补库存、不退券）
- HMAC 校验 `order_no|trade_no|amount|timestamp` + 时间偏差窗口；已 PAID 返回 200 + idempotent；
  CLOSED/CANCELLED 返回 409，且不改状态
- 测试：重复支付只生效一次、PAID 后取消被拒、签名错/金额错/超时回调被拒、关单后回调 409

## 卡点

无。

## 未验证（不许当成已完成）

- S3–S5 代码还没上服务器：公网仍是 S2 镜像，`/api/v1/orders` 仍是 404
- 前端静态资源还没部署：nginx 只反代 `/api/`，`/` 返回一行纯文本；按 plan 在 S7 一起做
- 支付、回调、HMAC（S6）
- compose 里的 worker/beat service、ACR 的 CI 构建推送、GitHub Secrets、部署与回滚演练（S7）
- 公网 demo 用户的安全初始化方式（S8）

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → 当前阶段文件（现在是 `docs/phases/phase6.md`，尚未创建）
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. 推 GitHub 要带本机代理 `-c http.proxy=http://127.0.0.1:10808`；推 Gitee 直连
4. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`；前端 `cd frontend && npm run dev`
   （本地栈的 api 容器占着 8000，跑 `runserver` 前先 `docker stop commerce-api`）
5. 压测：`cd backend && .venv\Scripts\python -m stocklab.bench`（结果手工贴进 phase 文件，不进 CI）
6. 异步关单本地演练（Windows 上 beat 与 worker 必须分两个进程）：
   `celery -A config worker -l info --pool=solo` 与 `celery -A config beat -l info`
