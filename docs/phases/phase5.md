# phase5 — S5 异步关单

> 阶段号与 `docs/plan.md` §11 的 S5 对应。阶段结束封口，不再追加；新内容进 phase6。

## 目标

把"超时订单自动关闭"做成一条可恢复的异步链路：beat 每分钟投递、worker 扫表、每单走与取消共享的
条件更新 service。要证明的不是"任务能跑"，而是三件事：

1. 真调度能关单，库存和券只回补一次；
2. 重复投递 / 并发关闭 / 取消与关单撞车时不产生第二次副作用；
3. worker 停掉、Redis 停掉再恢复时，行为有实测记录，不写没验证过的"必丢 / 绝不丢"。

## 范围

- `config/celery.py` + `config/__init__.py`：Celery 应用，broker 复用 `REDIS_URL`，不配 result backend
- `settings/base.py`：acks_late、prefetch=1、reject_on_worker_lost、ignore_result、软/硬超时 50/60、
  `visibility_timeout=120`、静态 beat 表（60 秒一次）
- `trade/rules.py`：加 `PENDING → CLOSED` 一行（副作用与取消相同）
- `trade/services.py`：抽出共享的迁移执行器 `_apply_transition`；`close_order`、`close_expired_orders`
- `trade/tasks.py`：`close_expired_orders(batch=100)` 薄封装，只做批量与计数
- 实验区反例 `stocklab/close_lab.py`：先查状态再回补的裸版，用来证明关单测试会红
- 测试：只关到期未支付、重复关单只回补一次、重复任务无副作用、批量上限、
  取消与关单并发只回补一次、支付后不被关、裸版反例双回补
- 真实演练：worker + beat 跑起来关掉一单；停 worker、停 Redis 再恢复，记录实际行为

## 明确不做

- 不做支付（S6）；`PAID` 的迁移在 S6 加，本阶段只保证关单不会碰已支付订单
- 不做 beat 的数据库 scheduler（`django-celery-beat`），定时表是静态配置
- 不做任务重试策略的玄学调参：业务异常不重试，也没有配 `autoretry_for`；任务抛错后不会自动重投，
  恢复靠下一拍扫描（见文末勘误），行为以演练结果为准
- 不在 Windows 上跑 prefork；演练用 `--pool=solo`，Linux 全栈留给 S7

## 门槛

- [x] 真调度能关单：worker + beat 跑起来后，到期订单变 CLOSED，库存与券回来
- [x] 并发关闭 / 取消同一单只回补一次，另一路拿到确定结果（200 或 409，不是 500）
- [x] 重复任务无副作用：同一批再跑一次，`closed=0` 且库存不变
- [x] 裸版反例能红：先查状态再回补的写法在并发下双回补，换成共享 service 后只回补一次
- [x] 停 worker、停 Redis 再恢复：行为有日志与数据记录，写清"观察到了什么"，不写绝对结论
- [x] `pytest` / `ruff` / `check_comments` / `check_lock` 全过

## 实施顺序

1. Celery 应用与 settings（含 `visibility_timeout` 的选择理由）
2. `rules.py` 加 CLOSED；`services.py` 抽迁移执行器 + `close_order` / `close_expired_orders`
3. `tasks.py` + beat 表；测试（含重复任务、批量、并发）
4. `stocklab/close_lab.py` 裸版反例 + 对照测试
5. 真实演练：正常关单 → 停 worker → 停 Redis → 恢复，逐个记录
6. 证据回填、`STATUS.md`、推送

## 实现级决定（先记理由再实施，AGENTS §1.3）

1. **`visibility_timeout=120`**。任务硬超时 60 秒、beat 间隔 60 秒；设成 2 倍硬超时后，
   一个已经跑满 60 秒被杀的 worker 不会在"可能还在跑"的窗口内被重投。plan §7.2 要求这个值由任务
   与调度语义推出来，不能抄 600；120 秒的代价是 worker 崩溃后最多 2 分钟才重投，对分钟级扫描可接受。
2. **不配 result backend**。`task_ignore_result=True`，任务返回值只用于测试和日志；关单的"结果"在
   数据库里（订单状态），不在 broker 里。少一个存储就少一处不一致。
3. **每单一个事务**，不是整批一个事务：一单失败不影响其它单已关掉的结果，也不会长时间持有锁。
4. **扫表只取 `order_no` 列表**（`values_list` + `[:batch]`，走 `(status, expire_at)` 索引），
   再逐单重新加条件更新；扫表时读到的状态只用来"挑候选"，不作为关闭依据。
   这与 plan §5 的"不能用先读 status 再 save"一致：读只用于筛选，判定在 `UPDATE ... WHERE` 里。
5. **关单与取消共用一个执行器**。`_apply_transition` 只认规则表里的行；两个入口的差别只有
   "谁有权限"和"是否要求已到期"，副作用不重复实现。
6. **关闭时写 `closed_at`**，取消时写 `cancel_reason`；两列在模型里本来就有，不新增字段。
7. **任务里不吞异常**。单笔关单失败（比如数据库异常）让任务整体抛错、留在日志里，等下一拍 beat
   重新扫到那单再关（实际不会自动重投，见文末勘误）；业务上"已取消/已支付"不是异常，返回 `None` 计入 `skipped`。
8. **Windows 演练用 `--pool=solo`**：plan §2.6 已写明 Windows 不跑 prefork，solo 能验证调度、
   任务执行、重投与恢复语义；线程池/进程池的差异留到 S7 的 Linux 全栈。

## 证据

### E1 关单服务（9 个用例）

```text
到期未支付才关   → 已支付的即使过期也不在候选里（scanned=1）；未到期的不动
关单副作用       → 库存回补、券回 UNUSED、closed_at 落库
重复关单         → 第二次返回 None，库存不再变
批量上限         → batch=2：先关 2，再关 1，第三次 scanned=0；三单最终都 CLOSED
Celery 执行      → close_expired_task.delay(batch=10).get() == {scanned:1, closed:1, skipped:0}
beat 表          → 指向 trade.tasks.close_expired_orders，间隔 60 秒
取消后再关       → 不重复回补，状态保持 CANCELLED
关单后再取消     → 409 ORDER_STATUS_INVALID，库存不变
并发（6 线程）   → 3 关 + 3 取消抢同一单：只发生一次迁移，
                   库存回到 10、version=2（扣 1 次 + 补 1 次，双补会是 3）
```

### E2 反例：先查状态再回补（`stocklab/close_lab.py`）

```text
2 线程同时关同一单 / 每单 2 件 / 初始库存 10，下单后 8
  裸版 close_unprotected → 两个线程都读到 PENDING，各回补 2 件
                          → 库存 8 → 12（比初始库存还多），两个都返回成功
  共享 close_order       → 只有一个赢家，库存回到 10
```

### E3 真实调度（本机 Windows，worker `--pool=solo` + beat 独立进程）

```text
12:56:46  worker 启动，注册 trade.tasks.close_expired_orders
12:57:46  beat: Sending due task close-expired-orders
          worker: received → succeeded in 0.047s: {'scanned': 1, 'closed': 1, 'skipped': 0}
         订单 OD…666666：待支付 → 已关闭，closed_at 12:57:46，库存 198 → 200
```

演练用 `ORDER_EXPIRE_MINUTES=0.05`（3 秒到期），生产默认仍是 15 分钟；两者不混写。

### E4 停 worker、停 Redis 的实测（不是推测）

**停 worker**：

```text
停掉 worker 后建单 OD…193537，等 75 秒
  → 订单仍是「待支付」；Redis 里 celery 队列长度 = 2（两拍任务排在 broker 里）
重启 worker
  → 13:01:49 连续收到 3 条消息：第一条 closed=1，后两条 scanned=0
  → 订单关闭，库存回到 200
```

结论：任务排队的载体是 broker，worker 回来会补做；beat 不依赖 worker 存活。

**停 Redis（broker 整个下线）**：

```text
13:03:34  worker: consumer: Connection to broker lost. Trying to re-establish...
13:03:38~13:05:02  Cannot connect ... Trying again in 2/4/6/8/10/12/14/16/18 秒（上限 100 次）
          → 进程没有退出，按指数退避重连
13:03:57  beat: Couldn't apply scheduled task close-expired-orders: SchedulingError
          → 这一拍的投递丢失；下一拍继续尝试
停机期间建单 OD…722878 → 下单不依赖 broker，创建成功、库存 198
13:05:20  Redis 恢复后 worker: Connected to redis://127.0.0.1:6379/0
13:06:06  下一拍：{'scanned': 1, 'closed': 1, 'skipped': 0} → 订单关闭，库存回到 200
```

这段只写观察到的行为，不下绝对结论：

- **丢的是投递，不是订单**：订单和 `expire_at` 在 MySQL 里，下一拍扫到就会关；所以 broker 丢消息
  不会让订单永远不关。
- **但恢复前的空窗期不会补**：13:03:57 那一拍确实没发出去，停机期间的到期订单要等恢复后的下一拍。
  说"消息一定不丢"或"丢了一定立刻补"都不成立。
- 关单延迟的上界因此是「最坏一次扫描间隔 + 恢复时间」，不是"实时"。

### E5 环境与检查

```text
pytest                          → 85 passed（新增 11：关单 9 + 反例 2）
ruff check / format --check      → 全过
python scripts/check_comments.py → 1.8%（上限 5%）
python scripts/check_lock.py     → lock=36 installed=36
新增依赖                          → celery 5.7.0 与 11 个传递依赖（kombu/amqp/billiard/vine/click…）全部钉版本
```

两个环境事实：

1. **Windows 上 Celery 拒绝 `-B`**（`-B option does not work on Windows`），beat 必须单独起进程；
   Linux 容器里可以用 `-B`，也可以拆成两个 service——S7 的 compose 里会拆。
2. worker 启动日志里 transport 显示 `redis://:**@127.0.0.1:6379/0`、`results: disabled://`，
   与"不配 result backend"的设定一致；密码由 Celery 自己打码，日志里没有明文。

## 勘误（2026-11-14）

原稿在"明确不做"第 3 条与实施决定第 7 条写的都是"DB 连接类异常由 broker 重投兜底"。
外部审查按实际加载的 Celery 5.7.0 任务属性核对了这句话，**原表述不成立**：

```text
acks_late = True            acks_on_failure_or_timeout = True
reject_on_worker_lost = True  autoretry_for = []
```

`acks_late` + `reject_on_worker_lost` 覆盖的是"worker 丢失"这一条路径（`worker/request.py`
对执行子进程丢失走 `reject(requeue=True)`），普通任务异常仍走确认分支，不会因为没有 `autoretry_for`
而重新入队。所以数据库短暂失败后的恢复，实际依靠的是**下一拍 beat 重新扫到仍处于 PENDING 且已过期的订单**，
不是原消息重投；`visibility_timeout=120` 也不是重投上界。

影响与保留：订单不会因为这句话而丢（订单和 `expire_at` 在 MySQL 里，E1 的"下一拍扫到就会关"仍然成立），
但"恢复了马上补"不成立，空窗期最长是一次扫描间隔加上停机时间。本阶段不改成有界重试——
S5 的取舍是"少一条重试路径就少一处不确定"，要加也必须有界并只针对特定异常，那属于新的决策。
原实验输出（E1–E5 的日志与数字）没有被改动。

