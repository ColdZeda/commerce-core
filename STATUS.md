# STATUS

> 更新于 2026-11-11（S3 收口）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S3 已完成**，代码在 `github.com/ColdZeda/commerce-core`（镜像 `gitee.com/ColdZeda/commerce-core`），
tag：`s0`、`s2`、`s3`；CI 每次 push 都绿（lint + test）。

**S3 下单主干**已经能跑通"登录 → 领券 → 进详情 → 下单 → 我的订单 → 取消"：

- 接口：`POST /orders`（201 / 幂等重放 200 + `X-Idempotent-Replay: 1`）、`GET /orders`、
  `GET /orders/{order_no}`、`POST /orders/{order_no}/cancel`
- 写链路：SKU 按 id 升序 `select_for_update` → 校验库存 → 服务端算金额 → 锁券校验门槛 →
  核销券 → 扣库存 → 写订单与明细快照；`client_token` 唯一索引 + 事务外回查
- 取消：`UPDATE ... WHERE status=PENDING` 的 rowcount 判赢家，只有赢家回补库存和退券
- 状态迁移写在 `backend/trade/rules.py`，S5/S6 只加行不改写法

**服务器**：`http://120.24.67.82:8080`，4 个容器（api/mysql/redis/nginx）healthy；
服务器上跑的仍是 **S2 镜像**，S3 的新接口还没部署（按 plan 在 S7 一起做）。

阶段记录：`docs/phases/phase0.md` / `phase1.md` / `phase2.md` / `phase3.md`；服务器事实与流水在仓库外
`..\ops\runbook.md` 与 `..\ops\server-log.md`。

## 下一步

**S4 库存深挖**。第一步先写 `docs/phases/phase4.md`（计划 + 门槛），再实施：

- B 方案乐观锁对照实现（`UPDATE ... WHERE version=? AND stock>=qty`，rowcount=0 限次重试）
- A/B/C 三方案的比较边界：单 SKU 扣减同边界比较，完整下单 p99 只比 A/B
- C 方案在 `experiments/` 用真实 Redis + Lua 跑通：预扣、重复预扣、补偿、对账，全部进 CI
- 真实 MySQL 并发下的守恒断言、失败码分布、故意破坏保护的"红灯"验证
- 实验报告：本机/服务器分开写，不把本机数字当线上结果

## 卡点

无。

## 未验证（不许当成已完成）

- S3 代码还没上服务器：公网仍是 S2 镜像，`/api/v1/orders` 现在 404
- 前端静态资源还没部署：nginx 只反代 `/api/`，`/` 返回一行纯文本；按 plan 在 S7 一起做
- 真实并发压测口径与 A/B/C 实验（S4）
- 支付/回调/关单与 Celery 超时关单（S5、S6）
- ACR 的 CI 构建推送、GitHub Secrets、部署与回滚演练（S7）
- 公网 demo 用户的安全初始化方式（S8）

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → 当前阶段文件（现在是 `docs/phases/phase4.md`，尚未创建）
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. 推 GitHub 要带本机代理 `-c http.proxy=http://127.0.0.1:10808`；推 Gitee 直连
4. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`；前端 `cd frontend && npm run dev`
   （本地栈的 api 容器占着 8000，跑 `runserver` 前先 `docker stop commerce-api`）
