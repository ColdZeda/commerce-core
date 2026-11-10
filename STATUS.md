# STATUS

> 更新于 2026-11-10（S2 收口 + 服务器换代）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0 / S1 / S2 已完成**，代码在 `github.com/ColdZeda/commerce-core`（镜像 `gitee.com/ColdZeda/commerce-core`），
tag：`s0`、`s1`（无）、`s2`；CI 每次 push 都绿（lint + test）。

**服务器已换成 commerce 在跑**：`http://120.24.67.82:8080`
- `/api/v1/health` → 200，`db` / `redis` 均 true
- `/api/v1/products` → 6 条；`/api/v1/coupons` → 3 条；`/admin/` → 404（C1）
- 4 个容器（api/mysql/redis/nginx），内存 used 741 / available 871 MB
- grounded-qa 全部容器已停（卷保留），服务器上只剩 commerce

阶段记录：`docs/phases/phase0.md` / `phase1.md` / `phase2.md`；服务器事实与流水在仓库外
`..\ops\runbook.md` 与 `..\ops\server-log.md`。

## 下一步

**S3 下单主干**。第一步先写 `docs/phases/phase3.md`（计划 + 门槛），再实施：

- A 方案行锁：固定 SKU id 升序加锁、校验库存、条件扣减
- 事务边界由 service 显式划定（`ATOMIC_REQUESTS=False`）
- 券核销：锁 `user_coupon`、校验门槛与有效期、原子置 USED
- 订单快照：`order` + `order_item`，金额服务端算，`client_token` 唯一索引 + 冲突后回查（在 `atomic` 之外）
- 接口：`POST /orders`、`GET /orders`、`GET /orders/{order_no}`、`POST /orders/{order_no}/cancel`
- 前端：商品详情页、结算、订单列表/详情/取消（四页链路）

## 卡点

无。

## 未验证（不许当成已完成）

- 前端静态资源还没部署到服务器：nginx 现在只反代 `/api/`，`/` 返回一行纯文本；按 plan 在 S7 一起做
- 下单、库存扣减、锁、幂等、订单状态机（S3）
- 真实并发压测口径与 C 方案实验（S4）
- 支付/回调/关单（S5、S6）
- ACR 的 CI 构建推送、GitHub Secrets、部署与回滚演练（S7）
- 公网 demo 用户的安全初始化方式（S8）

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → 当前阶段文件（现在是 `docs/phases/phase3.md`，尚未创建）
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. 推 GitHub 要带本机代理 `-c http.proxy=http://127.0.0.1:10808`；推 Gitee 直连
4. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`；前端 `cd frontend && npm run dev`
