# STATUS

> 更新于 2026-11-11（S4 收口）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S4 已完成**，代码在 `github.com/ColdZeda/commerce-core`（镜像 `gitee.com/ColdZeda/commerce-core`），
tag：`s0`、`s2`、`s3`、`s4`；CI 每次 push 都绿（lint + test）。

**S4 库存深挖**的四条结论：

- A 方案（行锁）在 200 请求 / 50 并发 / 100 库存下**卖完且守恒**，代价是热点行排队（单 SKU 扣减 p99 411ms）
- B 方案（乐观锁，3 次重试）同样不超卖，但热点上只成交 40/100；把重试提到 10 次能到 99/100，
  p50 从 197ms 涨到 629ms——重试预算买成交率，不是"B 更快"
- C 方案（真实 Redis + Lua）预扣、重复预扣、补偿、对账 11 个用例全进 CI，**不接主流程**
- 保护被拿掉时测试确实会红：裸版反例（20 个请求都读到库存 10、全部"成功"）＋一次手工删除
  `select_for_update` 把 `test_stock_is_never_oversold` 打成 `assert 12 == 5`，还原后变绿

实现在 `backend/stocklab/`（实验区，不进生产链路）；数字与口径见 `docs/phases/phase4.md`。

**服务器**：`http://120.24.67.82:8080`，4 个容器（api/mysql/redis/nginx）healthy；
服务器上跑的仍是 **S2 镜像**，S3/S4 的新代码还没部署（按 plan 在 S7 一起做）。

阶段记录：`docs/phases/phase0.md` … `phase4.md`；服务器事实与流水在仓库外
`..\ops\runbook.md` 与 `..\ops\server-log.md`。

## 下一步

**S5 异步关单**。第一步先写 `docs/phases/phase5.md`（计划 + 门槛），再实施：

- Celery worker/beat + Redis broker（`noeviction`、`acks_late`、`prefetch=1`、软硬超时 50/60）
- `close_expired_orders(batch=100)` 扫 `PENDING AND expire_at < now()`，走 `(status, expire_at)` 索引
- 每单调用与 `cancel_order` 共享的关单 service；`rules.py` 加一行 `PENDING→CLOSED`
- 裸版反例（先查状态再回补）＋并发关单/取消只回补一次；重复任务无副作用
- 真调度演练：停 worker、停 Redis 再恢复，记录实际重投行为，不写未验证的"必丢/绝不丢"

## 卡点

无。

## 未验证（不许当成已完成）

- S3/S4 代码还没上服务器：公网仍是 S2 镜像
- 前端静态资源还没部署：nginx 只反代 `/api/`，`/` 返回一行纯文本；按 plan 在 S7 一起做
- Celery 关单、worker/Redis 停止恢复（S5）
- 支付/回调/HMAC（S6）
- ACR 的 CI 构建推送、GitHub Secrets、部署与回滚演练（S7）
- 公网 demo 用户的安全初始化方式（S8）

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → 当前阶段文件（现在是 `docs/phases/phase5.md`，尚未创建）
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. 推 GitHub 要带本机代理 `-c http.proxy=http://127.0.0.1:10808`；推 Gitee 直连
4. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`；前端 `cd frontend && npm run dev`
   （本地栈的 api 容器占着 8000，跑 `runserver` 前先 `docker stop commerce-api`）
5. 压测：`cd backend && .venv\Scripts\python -m stocklab.bench`（结果手工贴进 phase 文件，不进 CI）
