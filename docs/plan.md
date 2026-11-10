# commerce-core 施工计划

> 由 `archive/final-plan-README-20261110.md` 迁移，2026-11-10。
> 本文是**唯一的施工基线**：做什么、做成什么样、什么顺序、什么门槛。
> 只描述"现在怎么做"。改动一律原地替换，不追加旧文；改动的理由、还原点写到 `docs/plan-changes.md`。
> 行为约束与红线在 `AGENTS.md`；当前进度在 `STATUS.md`；阶段记录在 `docs/phases/`。

## 0. 执行前先看这里

### 0.1 已定案，不要重新发起方案评选

- 项目名：`commerce-core`。
- 顶级目录：`E:\projects\commerce-core`；正式 Git 仓库：`E:\projects\commerce-core\repo`。
- 用户手动创建 GitHub 仓库 `commerce-core`；执行 agent 不擅自创建远程仓库。
- Django 5 + DRF + MySQL 8 + Redis + Celery + uWSGI + nginx + Vue 3 SPA + GitHub Actions + 阿里云 ACR。
- 6 张业务表 + Django 自带 User；14 个业务接口 + `/health`。
- 4 个前端路由，不为优惠券或订单详情增加路由。
- 库存：A 悲观锁主流程、B 乐观锁对照、C Redis 预扣独立实验。
- Redis 在正式链路中承担 **Celery broker**，不是只为 demo 存在。
- 关单只用 Celery beat 扫表；用户取消与超时关单共用 service；两个支付入口共用 service。
- 服务器不重置，两套 Compose 切换，同一时间只运行一套；优先不花钱、不要求两个项目同时在线。
- 不 clone 完整 MVP，不用 SQLite 做过渡，不用 GitHub Pages，不引入 AI、微服务、K8s、真实支付或短信。

---

## 1. 项目定位、核心闭环与验收优先级

### 1.1 一句话定位

一个可运行、可测试、可部署的电商交易闭环：用户登录、领券、按 SKU 下单、取消或模拟支付，超时订单自动关闭；库存不超卖，重复请求和异步任务不产生重复副作用。

### 1.2 要证明的能力

1. 在 Django/DRF 中正确划分事务边界，处理多表写入。
2. 用数据库约束、条件更新和幂等键解决真实一致性问题。
3. 实现并实验两种数据库库存方案，解释 Redis 预扣为何不是默认选择。
4. 让 Celery 异步任务可重复执行、可恢复、可验证。
5. 跑通 Vue → nginx → uWSGI → Django → MySQL，以及 beat → Redis → worker 链路。
6. 用 GitHub Actions 完成测试、镜像构建、部署、健康检查和回滚演练。

### 1.3 明确不做

注册、短信、第三方登录、真实支付、退款售后、购物车、地址簿、物流、图片上传、商品 ES 搜索、完整优惠券引擎、自定义 admin 业务后台、限流、Redis 页面缓存、监控告警全家桶、Flower、前端 TS/主题/响应式/骨架屏、覆盖率门槛、K8s、微服务、TCC/Saga、分布式锁、AI/RAG/Agent。

Django admin 只做受信任运营维护，不作为公开业务后台。不要为“以后可能需要”预留表、索引或三层 repository/DAO 架构；DRF + 清晰的 `services.py` 即可。

### 1.4 优先级不是砍掉 CI/CD

- **核心门槛**：S0–S3 + S5。必须能证明下单正确、库存一致、取消/关单幂等、任务可恢复。
- **完整交付门槛**：S0–S8 全部，包含 A/B 对照、C 实验、公网部署、完整 CI/CD、回滚和面试文档。
- 防止范围失控不等于把 CI/CD 变成可选；它仍是本项目目标。
- 新功能进入前必须指出删除哪一项等价工作；优先砍外围样式和附加实验，不牺牲核心正确性。

---

## 2. 总体架构与请求链路

### 2.1 正式部署进程

```text
浏览器
   │ HTTP，暂定公网 IP:8080
   ▼
nginx ───────────────→ Vue dist + collectstatic
   │ /api/、/admin/
   ▼
uWSGI → Django/DRF → MySQL 8（业务事实源）
             │
             │ 任务消息
             ▼
           Redis ← Celery beat 定时投递
             │
             ▼
        Celery worker → 调共享业务 service → MySQL
```

服务：`mysql`、`redis`、`api`、`worker`、`beat`、`nginx`，另有一次性迁移命令。`api/worker/beat` 共用后端镜像、不同入口；前端多阶段构建产物交给 nginx。不要在 ECS 上构建前端或后端镜像。

### 2.2 读链路

浏览器 → nginx 静态资源/history fallback → `/api/` 反代 → uWSGI → DRF → ORM → MySQL。

Redis 不做商品/订单缓存。列表页目标是 `count + 页数据`，商品详情用 prefetch 避免 N+1；实际 SQL 数用测试断言验证，不靠口头承诺。

### 2.3 下单写链路

Serializer 只校验输入格式，service 负责业务：

1. 如果带 `client_token`，先按 `(user_id, client_token)` 查已存在订单；命中直接返回原订单。
2. 显式 `transaction.atomic()`，固定 SKU id 升序加锁，避免多明细死锁。
3. 校验商品/SKU 上架、数量、库存，扣库存并更新 version。
4. 如有券，锁定用户券及必要关联记录，校验归属、未使用、有效期、门槛，并原子核销。
5. 服务端以 SKU 快照价计算总额、优惠和应付，绝不接受前端金额。
6. 写订单和明细快照，提交事务；201 在提交成功后返回。
7. 捕获同一 token 并发导致的唯一键冲突，安全回查并返回原订单；不能把冲突直接变 500。
8. 外部调用和异步投递不得夹在 DB 事务中；必须投递时使用 `transaction.on_commit`。

`ATOMIC_REQUESTS=False`，由 service 显式划边界。代价是漏写 `atomic` 不会自动兜底，必须用测试守住。

### 2.4 关单链路

beat 每 60 秒投递 `close_expired_orders` → worker 查 `PENDING AND expire_at < now()`，走 `(status, expire_at)` 索引、分批处理 → 每单调共享 `close_order` service → 条件更新 + 同事务回补库存和退券。

不用 `countdown=900`。原因不是“ETA 一重启必丢”这种绝对说法，而是 ETA 在 worker 调度、broker 重投及 visibility timeout 间有额外行为；数据库已持久保存订单和过期时间，扫表更简单、可恢复、可观察。分钟级延迟可接受，不写错误的“误差 0.07%”：60 秒扫描相对 900 秒窗口，最大附加延迟约 6.67%，平均约 3.33%，另加执行耗时。

### 2.5 支付链路

`/pay` 是明确的 mock 入口，配置 `ENABLE_MOCK_PAY`；`/payments/callback` 是模拟第三方回调，无 JWT，用 HMAC + 时间戳防伪造/重放。两者只调用同一个 `mark_order_paid(order_no, amount, ...)` service。

无真实支付、退款、对账能力。回调对已关闭/已取消订单返回 409 并记录错误；真实系统此时应进入退款/异常处理，本项目明确不做。

### 2.6 开发、预演、生产

| 项 | Windows 开发 | WSL2/本地全栈预演 | 阿里云生产 |
|---|---|---|---|
| Web | `runserver` | uWSGI + nginx | 同预演 |
| 前端 | Vite + `/api` 代理 | 构建后由 nginx 托管 | 同预演 |
| MySQL/Redis | Docker | Compose | Compose |
| MySQL 驱动 | 默认 PyMySQL + cryptography | 镜像 mysqlclient | 镜像 mysqlclient |
| Celery | 不跑 prefork；同步调用或进 Linux | worker + beat | worker + beat |
| DEBUG | True | False | False |
| 静态 | staticfiles | collectstatic + nginx | 同预演 |
| 配置 | 本地 `.env` | 本地私密配置 | 服务器 `/opt/commerce-core/.env` |

Windows 不运行 uWSGI，Celery 不用 Windows prefork。S7 前必须在 WSL2/Compose 以 uWSGI + nginx 跑通完整业务，不得只用 `runserver` 冒充部署验证。

---

## 3. 数据模型与迁移纪律

### 3.1 总约定

InnoDB、utf8mb4、UTC（`USE_TZ=True`）、BIGINT 主键、金额 `DECIMAL(10,2)`、状态 `SmallIntegerField + TextChoices`。MySQL 使用已验证的 8.0.30+ 固定补丁 tag，不用浮动 `mysql:8`。所有字段的 Django 类型在详细设计中展开，但不得改变下列约束。

### 3.2 六张业务表

| 表 | 关键字段 | 约束与索引 | 设计要点 |
|---|---|---|---|
| `product` | name, subtitle, description, cover_url, is_active, created_at, updated_at | `(is_active, -id)` | 封面外链；不上传 |
| `sku` | product FK, sku_code, title, price, stock, version, is_active, timestamps | `sku_code UNIQUE`，`CHECK stock>=0`，`product_id` 索引 | 价格与库存在 SKU；stock 有符号 INT + CHECK，不靠 UNSIGNED 报错 |
| `order` | order_no, user FK, status, total/discount/pay amounts, user_coupon FK NULL, expire_at, paid_at, closed_at, cancel_reason, client_token NULL, remark, timestamps | `order_no UNIQUE`，`(user,client_token) UNIQUE`，`(user,-created_at)`、`(status,expire_at)` 索引 | 对外用 order_no；expire_at 落库；client_token 支持重试 |
| `order_item` | order FK, sku FK NULL, sku_code, title, unit_price, qty, subtotal, created_at | `order_id` 索引，qty 正数 | 快照商品名、编码、价格；历史订单不受改价影响 |
| `coupon` | name, threshold_amount, discount_amount, total_qty, issued_qty, start_at, end_at, is_active, timestamps | `CHECK 0<=issued_qty<=total_qty`，`(is_active,end_at)` 索引 | 固定满减，不叠加不续期 |
| `user_coupon` | user FK, coupon FK, status UNUSED/USED, received_at, used_at, created_at | `(user,coupon) UNIQUE`，`(user,status)` 索引 | 每人每券一张；**无 order_id**；过期由 coupon.end_at 派生 |

外键：`order_item→order CASCADE`（仅防御，订单不物理删）、`order_item→sku SET_NULL`、`order→user PROTECT`、`order→user_coupon SET_NULL`、`sku→product PROTECT`、`user_coupon→coupon/user PROTECT`。

保留 `order→user_coupon` 单向事实，避免与 `user_coupon.order_id` 双向不一致。券退回不延长有效期；“已退回但过期”是合法状态。

### 3.3 必须覆盖的两条并发路径

- **领券**：唯一约束只挡同一用户重复领，不挡总量超发。需要在事务中以“条件增加 `issued_qty`（仍小于 total_qty）→ 检查 rowcount → 创建 user_coupon”完成；同用户重复返回 `COUPON_ALREADY_CLAIMED`，总量满返回 `COUPON_SOLD_OUT`，不能把数据库冲突变 500。
- **下单幂等**：唯一索引是最后防线，不是完整流程。两个同 token 请求同时未查到时，一方成功，另一方捕获唯一冲突后回查原订单并返回 200；body 与首次创建一致，可用 header `X-Idempotent-Replay: 1` 标识重放。

### 3.4 表数量口径与迁移

只计上述六张业务表。Django 的 `auth_*`、`django_migrations`、`django_admin_log`、content type 等框架表不计入。不启用 token blacklist、`django-celery-beat` 数据库 scheduler、Celery result backend，因此不为它们增加业务存储。

迁移默认只做加法：加表、加可空/有默认列、加索引。不直接删列、改类型、重命名。需要删除时先停用再下一版本删除。回滚代码不回滚数据库，旧代码必须能在新库上运行。

---

## 4. API 契约

### 4.1 通用规则

- 基线 `/api/v1`，`Authorization: Bearer <access>`，JSON；金额输出字符串，时间 ISO8601 带时区。
- 列表：`?page=&page_size=`，响应 `{count,next,previous,results}`，page_size 默认 10、上限 50。
- 排序白名单：商品仅允许 `created_at`、价格等显式字段，白名单外 400。
- 错误体统一 `{code,message,detail?}`，由全局 exception handler 收口；前端按稳定 code，不解析文案。
- 401 区分 `TOKEN_INVALID` 与 `TOKEN_EXPIRED`；他人订单按 404 处理，避免泄露单号存在性。

### 4.2 定案：14 个业务接口 + `/health`

| # | 方法与路径 | 鉴权 | 核心契约/错误 |
|---|---|---|---|
| 1 | POST `/auth/login` | 匿名 | username/password → access、refresh、user；401 |
| 2 | POST `/auth/refresh` | 匿名带 refresh | 新 access；401 |
| 3 | GET `/auth/me` | 登录 | 当前用户，供刷新页面恢复会话 |
| 4 | GET `/products` | 匿名 | 分页、keyword、白名单排序；含最低 SKU 价 |
| 5 | GET `/products/{id}` | 匿名 | 商品及 SKU/库存；404 |
| 6 | GET `/coupons` | 可选登录 | 可领券列表，登录时带 claimed |
| 7 | POST `/coupons/{id}/claim` | 登录 | 201；重复/售罄用 409 业务码 |
| 8 | GET `/me/coupons` | 登录 | `status=unused/used/expired`，分页 |
| 9 | POST `/orders` | 登录 | `{items:[{sku_id,qty}],user_coupon_id?,client_token?,remark?}`；201 或幂等重放 200 |
| 10 | GET `/orders` | 登录 | 仅本人、按状态筛选、分页 |
| 11 | GET `/orders/{order_no}` | 登录 | 详情和 items；404 |
| 12 | POST `/orders/{order_no}/cancel` | 登录 | PENDING→CANCELLED；已 CANCELLED 返回 200，其余冲突 409 |
| 13 | POST `/orders/{order_no}/pay` | 登录 + mock 开关 | PENDING→PAID；已 PAID 幂等成功 |
| 14 | POST `/payments/callback` | 匿名 + HMAC | 已 PAID 返回 200 + idempotent；CLOSED/CANCELLED 返回 409 |
| — | GET `/health` | 匿名 | db/redis 检查；失败 503 |

统一错误码至少包括：`VALIDATION_ERROR`、`AUTH_INVALID_CREDENTIALS`、`TOKEN_INVALID`、`TOKEN_EXPIRED`、`NOT_FOUND`、`STOCK_NOT_ENOUGH`、`PRODUCT_OFF_SHELF`、`COUPON_ALREADY_CLAIMED`、`COUPON_SOLD_OUT`、`COUPON_NOT_USABLE`、`ORDER_STATUS_INVALID`、`PAY_SIGN_INVALID`、`ORDER_NOT_PAYABLE`。

`client_token` 未传时 MySQL 唯一索引允许多个 NULL，但这不代表可忽略有 token 请求的冲突处理。支付回调校验 `order_no|trade_no|amount|timestamp` 的 HMAC、时间偏差与服务端应付金额；mock `trade_no` 不强制建支付流水表。

---

## 5. 订单状态机与共享 service

```text
创建订单 → PENDING
              ├─ 用户取消 → CANCELLED（终态，回补库存/退券）
              ├─ beat 超时 → CLOSED（终态，回补库存/退券）
              └─ /pay 或 /callback → PAID（终态，写 paid_at）
```

| 迁移 | WHERE 条件 | 同事务副作用 | 重复请求 |
|---|---|---|---|
| → PENDING | 商品/SKU 可售、库存足、券可用 | 扣库存、核销券、写订单/快照 | client_token 唯一 + 冲突回查 |
| PENDING→PAID | `status=PENDING` | 写 paid_at | 已 PAID 返回成功 |
| PENDING→CANCELLED | `status=PENDING` | 回补库存、券退 UNUSED | 已 CANCELLED 返回 200；PAID/CLOSED 409 |
| PENDING→CLOSED | `status=PENDING AND expire_at<now()` | 同上 | 已 CLOSED 无副作用返回 |

实现铁律：迁移用 `UPDATE ... WHERE identity=? AND status=?`，检查 rowcount。只有 rowcount=1 的赢家才能执行副作用，副作用与 UPDATE 同事务。用户取消和 beat 关单调用同一个 service，防止一边判状态一边忘记。

不能写成“先读 `if status==PENDING`，再保存并回补”，否则取消与关单并发时库存会双回补。PAID 后不自动退库存/券；正确业务是退款流程，本项目不做。

在 S3 前把允许的迁移与副作用整理成可单测的规则表；后续修改状态逻辑先跑规则与回归测试。

---

## 6. 库存三方案与实验边界

### 6.1 A：悲观锁，正式主流程

`atomic` 内按 SKU id 升序 `select_for_update` → 校验 `stock>=qty` → `stock-=qty`、`version+=1`。适合本项目多表事务，代码直观，无需重试；代价是热点行串行、等待者占 DB 连接、长事务放大锁时间。

MySQL 行锁等待参数是 **`innodb_lock_wait_timeout`**，不是 `lock_wait_timeout`。初始值与是否调小在服务器实测后确定；超时单独统计，不能伪装成库存不足。

### 6.2 B：乐观锁，对照实现

`UPDATE sku SET stock=stock-qty, version=version+1 WHERE id=? AND version=? AND stock>=qty`，rowcount=0 限次重试（初始最多 3 次 + 随机退避），必须保留 `stock>=qty` 兜底。

诚实结论：纯扣减时单条条件 UPDATE 本身就是原子 CAS，version 并不自动提升正确性；它主要在“读到的快照参与后续计算”时有价值。B 是对照组，不包装成更高级方案。

### 6.3 C：Redis 预扣，独立可运行实验

**不是主流程，不在公网启用，但必须有真实代码和 CI 测试。**

交付：

1. 真实 Docker Redis，不纯 mock；`experiments/` 可由 pytest 收集并进入 CI。
2. 一次 Lua/EVAL 原子完成“查订单预扣记录 → 查库存 → DECRBY → 写记录”，记录以 order_no 为键，含 sku、qty、状态、结果库存。
3. 禁止用“SETNX 占位后再 DECRBY”冒充完整幂等：占位后崩溃会让重试误报已扣。重复请求返回已存结果，不再次扣减。
4. 补偿另一次 EVAL，只在 `RESERVED` 时 `INCRBY` 并置 `COMPENSATED`，防双补偿。
5. 测试正常预扣、库存不足、并发预扣、重复预扣、DB 失败补偿、重复补偿、对账发现差异和一致时不误报。
6. 记录只用于实验和幂等/对账，不能用任意 TTL 破坏生命周期；建议覆盖订单生命周期（如 24h），实际值写入实验说明。
7. 对账不变量：`redis_stock == mysql_stock - Σ(RESERVED 状态 qty)`。已 COMMITTED 已计入 MySQL，已 COMPENSATED 已回到 Redis，不再算在途。差异只报告，不在语义未明时自动修。

C 要解释“扣了没落库”的窗口：Redis 成功而进程崩溃/DB 失败会少卖或产生差异；无持久化 Redis 重启还可能让库存复活。主流程选 DB 为唯一事实源，避免双写和对账成本。

### 6.4 A/B/C 如何比较

- **可跨方案比较正确性**：库存守恒、成功/失败数、失败码分布、最终差异数。
- **性能只在同一操作边界比较**：单 SKU 扣减操作；A 的锁+UPDATE、B 的条件 UPDATE、C 的 EVAL，连接/事务边界一致，计时包含 commit（A 行锁到 commit 才释放）。
- **完整下单 p99 只比较 A/B**；C 不参与，除非承担完全相同的订单持久化与副作用。
- 报告标题区分“单 SKU 扣减 p99”和“完整下单接口 p99”；全部注明本机/服务器、配置、连接数，不把本机结果冒充生产结果。

---

## 7. Celery、Redis broker 与关单实验

### 7.1 任务与配置

主任务：`close_expired_orders(batch=100)`，静态 beat schedule 每分钟执行。可有一个只写日志的 `notify_order_paid`，不是核心，时间紧张可砍。

初始配置：`task_acks_late=True`、`worker_prefetch_multiplier=1`、`task_reject_on_worker_lost=True`、`task_ignore_result=True`、soft/hard time limit 50/60、`broker_connection_retry_on_startup=True`、时区显式对齐。

`visibility_timeout` 必须根据任务及调度语义分析后配置，不能盲抄 600；记录为什么选它。业务异常不重试，DB 连接类异常有限重试并指数退避。任务至少一次投递，所有副作用必须幂等。

### 7.2 Redis broker 四个必须留下的决策与验证

1. **不持久化的边界**：Redis 无持久化可能丢队列，但 MySQL 保存订单/expire_at，下轮扫描仍能关单；说明这不等于所有消息都可以随便丢。
2. **`noeviction`**：内存满时写失败是可见错误，eviction 则可能静默丢任务；同步监控 `OOM command not allowed`，订单主流程不能把 broker 写失败当订单回滚理由。
3. **visibility timeout**：与执行和重投行为相关；必须验证 worker 异常停止后何时重投，不凭默认 1h 猜。
4. **至少一次**：任务可能重复，关单靠条件更新保证副作用一次。

### 7.3 S5 必做实验顺序

1. 在隔离测试/实验代码中保留一个裸版反例：先查状态再关单回补。
2. 多线程对同一订单触发关闭，观察双回补，证明反例测试能红。
3. 改共享条件更新 service，重跑证明只回补一次。
4. 补 `test_close_twice_only_once`、`test_cancel_and_close_race`。
5. 缩短 `ORDER_EXPIRE_MINUTES=1`，用真 beat/worker/Redis 做真实调度演练。
6. 分别停 worker、停 Redis，再恢复；观察业务数据、任务重投和日志，记录实际行为，不写未经验证的“必丢/绝不丢”。

---

## 8. 前端：四路由、三个券 UI 入口

技术：Vue 3 + Vite + Vue Router + Pinia + axios + Element Plus，JS，不上 TS，不做按需优化或设计系统。

| 路由 | 内容 |
|---|---|
| `/login` | 登录、保存 token、跳回 redirect 或商品页 |
| `/products` | 分页搜索商品；**可领券区域与领取按钮** |
| `/products/:id` | SKU、数量、选择已有券、提交订单；生成并复用 client_token |
| `/orders` | 状态 tab、取消、模拟支付；**我的券抽屉、订单详情抽屉** |

券的三个 UI 入口是“列表页领、详情页用、订单页看”，共用同一 API 和业务状态，不是三套逻辑。我的券不能新增 `/me/coupons` 前端路由。

`auth store` 持久化 access/refresh/user；刷新页面可通过 `/auth/me` 恢复会话。axios 请求加 Bearer；401 用模块级 `refreshPromise` 单飞刷新，排除 login/refresh 自身，失败清 store 并回登录页。错误按 code 映射中文，不直接把内部异常显示给用户。

JWT 使用 localStorage + 短 access，不启用 blacklist。明确代价：有 XSS 风险、不能服务端即时注销；不在本项目改 httpOnly/CSRF 方案。

开发 Vite 代理 `/api` 到 8000，生产 nginx 同源，因此无需额外 CORS 依赖。静态资源带 hash 可长缓存，`index.html` 必须 `no-store`，history fallback 到 index。禁止 tailwind、自定义主题、暗色、动画、骨架屏吞噬核心工期。

---

## 9. 测试策略与防假绿

栈：pytest + pytest-django；DRF 接口测试；真实 MySQL/Redis；不引 factory_boy、locust，不追求 QPS 或覆盖率门槛。简单 fixture 工厂与演示 seed 分开。

| 层 | 必测 |
|---|---|
| 纯业务 | 金额、券门槛/有效期、状态迁移规则、order_no |
| 模型/接口 | 唯一约束、鉴权、越权、分页筛选、错误码、快照、幂等重放 |
| 并发 | 不超卖、领券不超发、同 token 重复下单、取消 vs 关单、重复回调 |
| Celery | 重复执行无副作用、worker/Redis 停止恢复、真实调度 |
| C 实验 | 原子预扣、重复预扣/补偿、对账差异与无误报 |
| 前端 | 关键手工清单：登录、刷新、领用看券、下单、取消、支付、401 |

### 9.1 并发环境

用 `TransactionTestCase` 或 `django_db(transaction=True)`，真实 MySQL，独立线程连接，结束关闭连接；不能用 SQLite 验证行锁。普通 `TestCase` 可能让其他连接看不到未提交数据，造成 DoesNotExist，或 `.filter().first()` 得 None 后“什么都没发生”却满足“不超卖”。

### 9.2 断言纪律

无回补场景的守恒：

```text
初始库存 = 剩余库存 + Σ成功订单明细 qty
```

有回补场景：

```text
初始库存 = 剩余库存 + 成功预扣件数 - 已回补件数
```

必须断言确实创建成功订单、库存非负、无未解释 5xx、失败码分布符合预期、未预期数据库异常为 0。订单数与售出件数不是通用等价单位；仅在“每单 1 件、100 库存、200 请求、无其他合法失败”等明确场景才要求成功订单数=100。

`innodb_lock_wait_timeout` 超时单独计数，非零说明超过设计条件，压测结论作废重跑，不能记成“库存不足”。故障注入单独统计，不混入正常压测。

写完并发测试后临时删除 `WHERE stock>=qty` 或破坏条件更新，测试必须变红，随后恢复保护并再绿。没有这一步，不证明测试真有效。

### 9.3 压测口径与 CI

常规场景：200 请求 / 50 并发 / 100 库存，以及 5 件热点库存；每单数量必须明示。测试库和生产 `max_connections` 分别记录，不能写“200 并发”忽略连接上限。

报告只写环境、条件、成功/失败、错误码、守恒、耗时和延迟观察，不设 QPS 栏位。CI 默认跑 MySQL/Redis 服务和标记的并发实验；若 runner 反复不稳定，保留一个最小 CI 并发场景、全量本地必跑，并在 README 记录降级事实，不能悄悄删测试。

---

## 10. 部署、服务器切换与 CI/CD

### 10.1 服务器事实与约束

服务器是**阿里云轻量应用服务器 SWAS**，不是按标准 ECS 安全组操作；防火墙只能由用户在控制台手动修改，永不删除 SSH 22 规则。参考 `E:\projects\grounded-qa\ops\server-notes.md` 只提取通用事实，不能照搬 grounded-qa 专属配置。

旧记录：2 核、1.6GiB、2GiB swap、40GB 盘、Docker/Compose 已装、8080 曾开放。**这些都要开工时重新实测，不能当当前事实。**

无域名、无备案、无 HTTPS，暂定 `http://<公网IP>:8080`。8080 只是候选，不代表天然不冲突：grounded-qa 也曾使用它，必须先停旧栈并检查端口映射。

### 10.2 双 Compose 切换，不重置

保留 grounded-qa 代码、镜像、数据卷与独立备份；commerce-core 使用独立 project name、目录、网络、卷。示例项目名 `grounded` 与 `commerce`，实际以旧项目配置为准。

标准切换：

1. 确认当前 project、路径与卷，禁止盲目 `down -v`。
2. 停止旧栈全部容器（web、worker、定时任务等）。
3. `docker ps` 确认无旧容器/端口映射，`ss -ltnp` 确认目标端口无残留监听。
4. 启动新栈，执行健康检查及业务冒烟。
5. 切回时反向执行，确认 grounded-qa 页面/API 和数据恢复。
6. 永不执行 `docker system prune --volumes`、`docker volume prune` 等可能误删数据的命令。

Compose 切换不等于备份。S2 若切回失败，立即暂停后续服务器操作，恢复 grounded-qa 并重新让用户决定，不得强行继续。

### 10.3 内存预算和降级

以下为**待实测初始预算**，不是承诺：

| 组件 | 初始约束 | 目标 RSS |
|---|---|---|
| OS + Docker | 不盲目关安全/云助手 | 200–300MB |
| MySQL | buffer pool 128M、performance_schema OFF、max_connections 50 等 | 320–450MB |
| Redis | maxmemory 64M、noeviction、按 broker 语义决定持久化 | 10–25MB |
| api | uWSGI 2×2、max-requests、harakiri | 120–180MB |
| worker | concurrency=1、max-tasks-per-child | 90–140MB |
| beat | 单实例 | 55–80MB |
| nginx | 单 worker | 8–15MB |
| **合计** | | **约 0.80–1.15GB** |

S2 用 `docker stats --no-stream`、`free -m`、MySQL 状态实测，不能用旧记录或算术估计代替。内存不足按以下顺序逐级、记录代价：

1. beat 合并 worker（`-B`），省内存但降低独立性；
2. uWSGI 改 1 process / 4 threads，吞吐和阻塞隔离下降；
3. MySQL buffer pool 64M、评估关 binlog，慢查询/恢复能力下降；
4. 仍不足再让用户决定升级配置，不擅自花钱或删除核心 Celery 目标。

### 10.4 CI/CD

GitHub 主仓库，Gitee 仅作国内镜像；GitHub Actions + 阿里云 ACR，不默认 GHCR。Secrets/ACR 凭据由用户后续提供，不能写入聊天、Git 或文档。

流水线：

```text
push / PR
 ├─ lint：ruff（后端），前端基础检查
 ├─ test：MySQL/Redis services + pytest + C 实验 + 最小并发用例
 ├─ build：后端镜像、前端/静态产物镜像，固定 sha tag
 ├─ push：阿里云 ACR
 └─ deploy：main → SSH → pull → migrate → up -d → health → 必要时回滚
```

- 镜像绝不在服务器 build；1.6GiB 容易 OOM。
- 迁移在 `up -d` 前用一次性容器执行，遵守加法迁移。
- GitHub Secrets 只放部署/镜像仓库凭证；业务密钥放服务器 `/opt/commerce-core/.env`，人工创建，CI 不覆盖。`.env.example` 只列 key 和安全示例。
- 保存 current/previous image tag，回滚切回上一可用 tag；S7 必须真实演练一次回滚。
- 单机 Compose 重建会有短暂不可用，不宣称零停机。

### 10.5 uWSGI/nginx 验证项

uWSGI 锁定经过验证的具体版本，不写“必须 2.0.24+”的错误前提。S0 在 Linux 镜像中实际 import、启动 worker 并访问 Django，失败才讨论 gunicorn 兜底；目标仍是 uWSGI。

初始参考：2 process / 2 thread、`harakiri=30`、`max-requests=1000`、`die-on-term=true`；nginx `uwsgi_read_timeout` 与 harakiri 对齐、history fallback、gzip、合理 body size、日志大小上限。每个最终参数要留下理由或实测，不能机械抄配置。

---

## 11. 阶段与门槛（没有日期）

每个阶段先写/更新计划与验收记录，再实施；遇到失败先修，不堆下一阶段功能。以下“完成”必须有证据，不是代码文件存在。

每阶段的记录写在 `docs/phases/phaseN.md`，与本表阶段号一一对应（S0 → `phase0.md`）。阶段结束封口，不再追加。

| 阶段 | 工作内容 | 完成门槛 |
|---|---|---|
| **S0 基线** | 顶级目录与 repo、AGENTS/README/阶段文档、Django/Vite 官方骨架、MySQL/Redis Compose、配置与 `.env.example`、health、ruff/pytest、CI 初线、驱动与 uWSGI 实测 | `compose up` 后 health 的 db/redis 为 true；Windows 可连 MySQL；Linux 镜像中 uWSGI 实际启动；CI 绿；依赖锁版本；不写业务代码抢跑 |
| **S1 商品/SKU** | 六表模型与迁移、admin、商品列表/详情、seed、索引和查询检查 | 商品可浏览；分页/筛选正确；迁移可重复执行；列表无 N+1（用 assertNumQueries 实证）；admin 可维护价格库存 |
| **S2 登录/券 + 公网冒烟** | JWT login/refresh/me、券列表/领取/我的、领券并发约束、前端登录与券入口、401 单飞；最小 mysql/api/nginx 上服务器 | 重复领券/超发有正确业务码；刷新页面不掉登录；**并发领券测试通过**；停 grounded→部署→外网可达→记录内存→停 commerce→切回 grounded 并验证恢复；不测尚未完成的下单 |
| **S3 下单主干** | A 行锁、事务、券核销、订单快照、client_token、订单列表/详情/取消、四页核心链路 | 下单金额/库存正确；改价不影响历史订单；同 token 并发只一单且重放可返回；取消只回补一次；规则表和回归测试绿 |
| **S4 库存深挖** | B 对照、A/B/C 实验边界、真实 MySQL 并发、C 的真实 Redis/Lua/补偿/对账、实验报告 | 守恒/成功订单/错误码断言全过；保护被故意破坏时测试能红；C 全部实验进 CI；A/B 完整下单与同边界扣减结果分开记录 |
| **S5 异步关单** | worker/beat/Redis broker、共享关单 service、重试与可见性、裸版反例、停止恢复演练 | 真调度能关单；并发关闭/取消只回补一次；重复任务无副作用；worker/Redis 停止恢复行为有实测记录 |
| **S6 模拟支付** | `/pay` 和 `/callback` 共用 mark_order_paid、HMAC/时间戳、状态校验 | 重复支付/回调只生效一次且按契约返回；CLOSED/CANCELLED 不误改；签名/金额/状态测试完整 |
| **S7 部署与 CI/CD** | 完整 Compose、静态资源、WSL2 全栈、ACR、Actions 全链路、部署密钥、回滚 | 公网完成登录→领券→下单；分别用待支付订单验证取消/超时关单，用另一订单验证支付及 PAID 后取消被拒；一次 push 自动部署；健康检查有效；手动回滚成功；切回 grounded 仍可用 |
| **S8 收尾** | README、架构/契约/状态机/测试/部署/压测/取舍文档、演示数据、面试讲述与四格表 | 新用户按 README 可跑通；文档数字有实测来源；能演示核心失败→修复；明确项目级而非生产级，不虚构指标 |

### 阶段依赖

- S0 解决驱动、基础镜像和 CI，不把环境问题拖到最后。
- S2 只提前验证环境与切换，不提前实现 S3 下单。
- S3 同步闭环必须先于 S5 异步，避免同时调事务和 Celery。
- S4 的性能数字不能越过相同操作边界原则。
- S7 再做完整 CI/CD，但 CI 从 S0 已存在并逐阶段扩展。

---

---

## 12. 风险、取舍与面试纪律

| 风险 | 具体失败路径 | 控制 |
|---|---|---|
| 范围膨胀 | 加购物车/地址/后台，核心并发没测完 | 白名单；加一必须删一 |
| 内存与 swap | 接口偶发超时，被误判业务 bug | S2 冒烟、实测预算、逐级降级 |
| 并发假绿 | 数据不可见或请求全失败，仍满足“不超卖” | 真实 MySQL/事务、成功订单与守恒断言、故意破坏保护 |
| 双回补 | 取消与关单都先读 PENDING | 共享条件更新 service，rowcount 赢家才副作用 |
| 领券超发 | 唯一约束只挡同人重复，不挡总量 | 条件增加 issued_qty + 事务 + 并发测试 |
| 同 token 重复单 | 先查不到，双方同时插入 | 唯一索引 + 捕获冲突回查，不返回 500 |
| Redis 实验假幂等 | SETNX 后崩溃，重试误报已扣 | 单 EVAL 原子预扣与记录 |
| 错误性能比较 | C 只 DECR，却和 A/B 完整下单比 p99 | 相同操作边界、计时含 commit、报告分题 |
| Redis broker 静默异常 | evict/visibility 配置让任务消失或很晚重投 | noeviction、日志、停止恢复实测 |
| 服务器切不回去 | 旧容器/端口未清、卷误删、环境被改 | S2 完整往返演练，卷操作红线，独立备份 |
| 密钥事故 | `.env` 或 ACR/SSH 私钥进 Git/聊天 | secrets 分工、人工服务器 env、提交前检查 |
| 前端时间黑洞 | 401/券入口/抽屉/状态细节超过预期 | 四路由、默认组件、无主题、按清单验收 |

### 面试表达

重点不是“我会多少组件”，而是能拿出失败现场和证据：

- 为什么订单明细要快照？
- 为什么唯一约束不足以完成领券和下单幂等？
- 取消与关单并发时，双回补怎么复现、怎么修？
- 为什么乐观锁 version 对纯扣减可能是冗余？
- 为什么 C 做了真实实验仍不接主流程？
- 为什么 broker 不持久化在本关单设计里可接受，边界是什么？
- 为什么不能拿 C 的 DECR p99 对比 A/B 完整下单？
- 为什么镜像在 CI 构建、迁移只加法、回滚不回库？
- 双 Compose 切换如何证明 grounded-qa 能恢复？

Django/MySQL/Celery 是**项目级实操**；不能包装成大型生产高并发经验。不要写 QPS 口号、零停机、生产级 Redis 库存系统。生产相关经历只按其他已有项目的真实事实叙述。

---

