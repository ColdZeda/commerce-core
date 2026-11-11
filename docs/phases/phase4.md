# phase4 — S4 库存深挖与三方案实验

> 阶段号与 `docs/plan.md` §11 的 S4 对应。阶段结束封口，不再追加；新内容进 phase5。

## 目标

把"库存不超卖"从一句结论变成三件可查的事：

1. **A 方案（悲观锁）在真实并发下守得住**，而且守得住这件事能被证明——把保护拿掉，测试必须变红。
2. **B 方案（乐观锁）是同口径对照**，不是"更高级的方案"；它的成败与边界有数字。
3. **C 方案（Redis 预扣）有真代码、真 Redis、真 Lua、补偿与对账**，全部进 CI，但**不接主流程**。

## 范围

- `backend/stocklab/`（实验区，不参与生产链路）
  - `deduct.py`：A 扣减对照、B 乐观锁（version CAS + `stock>=qty`，限次重试）、裸版反例（先读后写）
  - `orders.py`：B 的完整下单（单 SKU、无券；实验边界写死在 docstring 里）
  - `redis_reserve.py`：C 方案的 Lua 预扣 / 提交 / 补偿 / 对账
  - `bench.py`：手工压测脚本（200 请求 / 50 并发 / 100 库存，以及 5 件热点场景）
  - `tests/`：A/B 守恒、反例变红、C 的八个实验、对账
- 证据：守恒断言、成功单数与失败码分布、故意破坏保护的红色结果、三方案的延迟原始数字

## 明确不做

- 不把 B 或 C 接进 `POST /orders`（plan §6.1 主流程仍是 A）
- 不做分布式锁、不引入 Redis 事务性持久化配置、不讨论集群
- 不写 QPS 口号；报告只有环境、条件、成功/失败、错误码、守恒、耗时与延迟
- 不做 C 方案的自动修复对账（只报告差异，plan §6.3.7）

## 门槛

- [x] A/B 并发守恒断言全过（200 请求 / 50 并发 / 100 库存，以及 5 件热点）
- [x] 成功订单数与失败码分布符合预期；未预期 5xx / 数据库异常为 0
- [x] 保护被故意破坏时测试变红（裸版反例 + 一次性手工变异各一份证据）
- [x] C 方案全部实验进 CI：预扣、库存不足、并发预扣、重复预扣、DB 失败补偿、重复补偿、对账一致与不一致
- [x] A/B 的"完整下单"与"同边界单 SKU 扣减"结果分开记录，不混成一栏
- [x] `pytest` / `ruff` / `check_comments` / `npm run lint` 全过

## 实施顺序

1. `stocklab/deduct.py` + `orders.py`：A/B/反例三条路径
2. A/B 并发守恒测试（真实 MySQL、独立线程连接、50 并发）
3. 手工变异验证（删 `stock>=qty` → 红 → 恢复 → 绿）
4. `stocklab/redis_reserve.py`：Lua 预扣/提交/补偿 + 对账，八个测试
5. `bench.py` 跑原始数字；A/B 完整下单与单 SKU 扣减分开测
6. 证据回填、`STATUS.md`、推送

## 实现级决定（先记理由再实施，AGENTS §1.3）

1. **实验目录放 `backend/stocklab/`，不放仓库根 `experiments/`**。plan 只写了"`experiments/` 可由 pytest
   收集并进入 CI"，但本仓库的 `testpaths`、`ruff check .`、`check_comments.py backend` 三个入口都以
   `backend/` 为根；放根目录要同时改三处配置并给 pytest 加 `sys.path` 兜底，才能让实验代码被收集和被 lint。
   放 `backend/stocklab/` 一行配置都不用改，实验代码照样被收集、被 lint、被注释检查。记录见
   `docs/plan-changes.md` D-006。
2. **B 只做对照，不进主流程**。`version` CAS 之外必须保留 `stock>=qty`：纯扣减时单条条件 UPDATE 本身就是
   原子 CAS，`version` 的价值在于"读到的快照参与后续计算"，这一点在报告里直说，不包装成更高级。
3. **B 的完整下单只覆盖单 SKU、无券路径**。多 SKU 与券会让"扣减策略"和"其它业务规则"的耗时混在一起；
   边界写在函数 docstring 和报告里，A 的完整下单则原样调用生产 `create_order`。
4. **Redis 键统一 `lab:` 前缀，测试只删自己的键**。本机 Redis 将来还要当 Celery broker，测试里绝不
   `FLUSHDB`；每个用例前后按前缀清理，互不干扰。
5. **预约记录 TTL 24 小时**（plan §6.3.6 的建议值，覆盖订单生命周期）；状态只有
   `RESERVED → COMMITTED / COMPENSATED`，每次迁移都由 Lua 里的状态判断把住，重复调用不改状态。
6. **对账只报告**：`redis_stock` 与 `mysql_stock - Σ(RESERVED qty)` 不一致时输出差异行，不自动修——
   语义未明时自动修会把一次排障变成一次数据破坏。
7. **压测脚本不进 pytest**：CI 只跑正确性并发用例，避免性能波动导致假红；脚本手工运行，结果原样贴进证据。
8. **反例是独立实现**，不是"注释掉某行"的开关：`deduct_unprotected` 先读后写、不加锁不加条件，
   测试断言它会破坏守恒，同时断言生产路径不会——两个断言放在同一个文件里，谁失效都看得见。

## 证据

### E1 A/B 并发守恒（真实 MySQL，独立线程连接）

四个用例（`stocklab/tests/test_a_b_conservation.py`）断言的是不变量，不是某一次的运气：

```text
200 请求 / 50 线程 / 100 库存 / 每单 1 件
  A  恰好 100 成功、100 STOCK_NOT_ENOUGH、剩余 0、剩余 + 成功 = 100
  B  成功 + NOT_ENOUGH + RETRY_EXHAUSTED = 200，且 剩余 = 100 - 成功（一件都不多卖）

5 件热点 / 120 请求 / 50 线程
  A  恰好 5 成功、115 NOT_ENOUGH、剩余 0

同场景对照（20 库存 / 40 请求 / 20 线程）
  A  20/20 成交、剩余 0
  B  成交少于 20、剩余 + 成交 = 20（3 次重试在 20 路热点下不够用）
```

B 的"卖不完"不是缺陷，是有限重试的必然结果：每个请求最多试 3 次，版本被别人改过就放弃。
它换来的是不排队等锁；代价是热点行上的成交率。这条口径写进报告，不写成"A 更好"。
具体成交数与延迟见 E4。

### E2 保护被拿掉时测试会红（两种证明）

**反例对照（实验区内的独立实现）**：

```text
20 线程 / 10 库存 / 先读后写不加锁
  → 20 个请求都读到"库存 10"，全部返回成功，最终库存 9
  → 9 + 20 != 10，守恒断言失败（测试通过：它本来就该失败）

同一场景换回 A（select_for_update）
  → 10 成功、10 NOT_ENOUGH、剩余 0、10 + 0 = 10
```

**一次性手工变异（拿掉生产代码里的锁）**：把 `trade/services.py` 的 `select_for_update()` 去掉，
`test_stock_is_never_oversold` 立刻变红：

```text
assert sum(1 for kind, _ in results if kind == "order") == 5
E   assert 12 == 5
```

`git checkout -- backend/trade/services.py` 还原后同一个用例变绿。变异过程不留在代码里，
只留这条记录——留着开关比没有开关更危险。

### E3 C 方案（真实 Redis + Lua，11 个用例）

```text
预扣            → RESERVED，库存 5 → 3                 test_reserve_decrements_redis_stock
库存不足        → INSUFFICIENT，库存不变、不写记录        test_reserve_rejects_more_than_stock
未装载库存      → NO_STOCK                              test_reserve_without_loaded_stock_is_reported
重复预扣        → ALREADY_RESERVED，库存不再减           test_duplicate_reserve_returns_stored_result...
并发预扣        → 50 请求 / 20 线程 / 20 库存 → 20 成功、30 INSUFFICIENT、库存 0
补偿            → COMPENSATED，库存回到 5；再补偿 SKIPPED_COMPENSATED，库存不变
落库失败后补偿  → 模拟 DB 异常 → 补偿把库存退回 5
提交后再补偿    → SKIPPED_COMMITTED，库存不回退
对账一致        → []；提交后把 MySQL 也减 2，仍然 []
对账差异        → 手工把 Redis 库存 +3 → 报 1 行 diff=3，且不自动修
未装载的 SKU    → 不参与对账
```

### E4 压测原始数字（本机，2026-11-11）

环境：Windows 11 + Docker Desktop；MySQL 8.0.43 容器（`read committed`、`innodb_lock_wait_timeout=10`、
buffer pool 128M、`max_connections=120`）；Redis 7.4.2 容器（`maxmemory 64mb`、`noeviction`）；
Python 3.12 + PyMySQL；50 条线程各自连接；200 请求 / 50 并发 / 100 库存 / 每单 1 件。

| 场景 | 成功 | 失败 | 剩余库存 | p50(ms) | p95(ms) | p99(ms) | 总计(s) |
|---|---|---|---|---|---|---|---|
| A 单 SKU 扣减 | 100 | NOT_ENOUGH×100 | 0 | 253.4 | 389.4 | 411.3 | 1.06 |
| B 单 SKU 扣减（3 次重试） | 40 | RETRY_EXHAUSTED×160 | 60 | 196.6 | 406.1 | 472.3 | 0.98 |
| B 单 SKU 扣减（10 次重试） | 99 | RETRY_EXHAUSTED×101 | 1 | 629.1 | 901.8 | 1008.5 | 2.38 |
| C Redis EVAL 预扣 | 100 | INSUFFICIENT×100 | 0 | 13.6 | 96.8 | 100.8 | 0.15 |
| A 完整下单 | 100 | STOCK_NOT_ENOUGH×100 | 0 | 475.2 | 732.6 | 765.1 | 1.98 |
| B 完整下单（单 SKU 无券） | 13 | RETRY_EXHAUSTED×187 | 87 | 361.3 | 455.4 | 461.8 | 1.60 |

怎么读这张表：

- **A 卖完 100 件且守恒**，代价是热点行排队：单 SKU 扣减 p99 411ms 里绝大部分是等锁。
- **B 的 p50 更低但成交更少**：3 次重试只成交 40 件。把重试提到 10 次能卖到 99 件，
  p50 从 197ms 涨到 629ms——这就是"重试预算买成交率"的具体价格，不是"B 更快"。
- **C 最快（p99 101ms）且没超卖，但什么都没落库**：它只证明预扣这一段能原子完成，
  不能据此说下单更快；C 的完整链路要加上落库、补偿、对账，那是另一笔成本。
- **A/B 的完整下单分开放**：B 的完整下单只有单 SKU 无券路径（实验边界），不能和 A 的全功能路径
  当成同一口径的胜负。

`max_connections` 三处不同，写清楚：压测库 120（本次调高）、生产 compose 50（2 vCPU / 1.6 GiB 的预算）、
CI 镜像默认 151。本机数字不代表线上，只用于同机同配置下的横向比较。

### E5 本机检查

```text
pytest                          → 74 passed（新增 stocklab 17：守恒 4、反例 2、C 方案 11）
ruff check / format --check      → 全过
python scripts/check_comments.py → 1.6%（上限 5%）
前端未改动，npm run lint 沿用 S3 结果
```
