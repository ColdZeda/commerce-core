# phase3 — S3 下单主干

> 阶段号与 `docs/plan.md` §11 的 S3 对应。阶段结束封口，不再追加；新内容进 phase4。

## 目标

把"下单"做成可证明正确的一条写链路：金额只由服务端算、库存不超卖、券只核销一次、
同一个 `client_token` 并发重试只落一单、取消只回补一次库存。同步链路先立住，
后面的异步关单和支付才有一致的底座。

## 范围

- `trade` app：
  - `POST /orders`（201 创建 / 200 幂等重放，`X-Idempotent-Replay: 1`）
  - `GET /orders`（仅本人、`status` 筛选、分页）
  - `GET /orders/{order_no}`（他人订单按 404，不泄露单号存在性）
  - `POST /orders/{order_no}/cancel`（`PENDING→CANCELLED`；已取消返回 200；其余 409）
- 下单 service（`trade/services.py`）：显式 `transaction.atomic()`、SKU 按 id 升序
  `select_for_update`、校验库存、服务端算金额、锁 `user_coupon` 并原子核销、
  写订单与明细快照
- 状态迁移规则表（`trade/rules.py`）：把"允许哪些迁移、各自带哪些副作用、重复请求怎么处理"
  写成可单测的数据，service 和测试共用同一份，避免一处改状态一处忘记补副作用
- 前端：`/products/:id`（SKU、数量、选券、提交）、`/orders`（状态 tab、详情抽屉、
  取消、我的券抽屉）；`/products` 补上进入详情的入口

## 明确不做

- 支付、支付回调、mock 支付开关（S5）
- Celery 关单、超时扫描（S6）；本阶段只保证 `cancel_order` 就是将来关单要复用的那个 service
- B 方案乐观锁、C 方案 Redis 预扣（S4，实验目录）
- 退款、部分取消、改单、库存回滚以外的售后语义
- 前端静态资源上线（S7）

## 门槛

- [x] 下单金额与库存正确：金额只由服务端按 SKU 当前价算，客户端传金额被忽略
- [x] 改价不影响历史订单：下单后改 SKU 价格，订单详情与快照不变
- [x] 同 `client_token` 并发只落一单，重放返回同一单号
- [x] 取消只回补一次：重复取消、取消与"已支付/已关闭"冲突都有确定结果
- [x] 库存不超卖：并发下单同一 SKU，成功单数 == 扣减总量，库存不为负
- [x] 规则表与回归测试绿；`pytest` / `ruff` / `check_comments` / `npm run lint` 全过

## 实施顺序

1. `trade/rules.py` 规则表 + 纯业务测试（迁移、副作用、重复请求语义）
2. `trade/services.py`：`create_order` / `cancel_order` / `order_no`
3. 序列化、视图、路由；接口测试
4. 并发测试（真实 MySQL、独立线程连接）
5. 前端三页与路由、导航
6. 本地手工验证 → 证据回填 → `STATUS.md` → 推送

## 实现级决定（先记理由再实施，AGENTS §1.3）

1. **`order_no` 格式**：`OD` + `YYYYMMDDHHMMSS` + 6 位随机数字，共 22 字符（字段上限 32）。
   带时间便于人工定位，随机尾数避免同秒碰撞；唯一索引兜底，撞号时在保存点内重生成一次。
   不用自增 id 对外暴露单量，也不用 UUID（不好念、不好查）。
2. **同一 `client_token` 的回查放在 `atomic` 之外**。事务里捕获唯一冲突后再查，
   读到的是本事务的快照，查不到自己刚插失败的行，反而把"重放"变 500（C5）。
3. **金额与优惠**：`total = Σ(单价 × 数量)`，`discount = min(券面额, total)`，
   `pay = total - discount`。券面额大于订单金额时按"不找零"截到 total，
   而不是让 `pay` 变负数——项目里没有余额体系，负数应付没有落点。
4. **重复 SKU 直接拒绝**（`VALIDATION_ERROR`），不在服务端静默合并数量：
   合并会让"我提交了 2 行"和"实际 1 行 × 2 件"在快照里看不出差别，契约不如显式报错清楚。
5. **订单过期时间**：`ORDER_EXPIRE_MINUTES`（默认 15，来自运营规则）写入 `expire_at` 落库，
   不用"读的时候按 created_at 现算"，否则 S6 的关单扫描没有可用的索引条件。
6. **回补库存用 `F()` 单语句 +`version+1`**，按 `sku_id` 升序逐条执行，
   与下单的加锁顺序一致，避免取消与下单互相等待成环。
7. **取消的"赢家"判定用条件更新 rowcount**（`WHERE id=? AND status=PENDING`），
   不是"先读 status 再 save"；只有 rowcount=1 的那次才回补库存、退券，副作用同事务。

## 证据

### E1 规则表（4 个用例）

```text
trade/tests/test_rules.py
→ PENDING→CANCELLED 的副作用集合 == {restock, return_coupon}
→ 表里所有迁移的 source 都是 PENDING（终态没有出边）
→ 表里声明的每个 effect 都能在 services.EFFECTS 找到实现（防"声明了没实现"）
→ 取消查的就是这张表，没有第二套状态判断
```

### E2 下单主干（服务层 10 个用例）

```text
2 件 × 30.00 + 满 50 减 10   → total 60.00 / discount 10.00 / pay 50.00；券 USED 且 used_at 非空
只有 30.00 用满 50 的券       → COUPON_NOT_USABLE；库存仍 10、无订单、券仍 UNUSED（整笔回滚）
券面额 100 > 订单 30         → discount 截到 30.00、pay 0.00（不找零）
用别人的券                    → COUPON_NOT_USABLE
库存 3 买 5                   → STOCK_NOT_ENOUGH；库存不变、无订单
下架 SKU / 不存在 SKU         → PRODUCT_OFF_SHELF
下单后改价、改标题、改编码     → 明细仍是 30.00 / 默认规格 / 旧 sku_code（快照不受影响）
买 3 件                       → stock 10→7、version 0→1
expire_at                     → created_at + 15 分钟（±5 秒）
order_no                      → OD + 20 位数字，两次下单不同
```

### E3 接口契约（8 个用例）

```text
POST /orders 未登录            → 401 TOKEN_INVALID
POST /orders                  → 201；金额是字符串；items 带 sku_code 快照；remark 原样返回
同 client_token 再发一次        → 200 + X-Idempotent-Replay: 1，order_no 相同，库存只扣一次
同单重复 SKU / 空 items        → 400 VALIDATION_ERROR
GET /orders                   → 只含本人；?status=paid 精确过滤；非法 status → 400
GET /orders/{别人的单号}        → 404 NOT_FOUND
POST /orders/{no}/cancel      → 200 已取消、cancel_reason 落库；再取消 200 且副作用只发生一次
已 PAID 再取消                 → 409 ORDER_STATUS_INVALID，库存不回补
```

### E4 并发（真实 MySQL，独立线程连接，2026-11-11）

```text
test_same_client_token_creates_exactly_one_order
  8 线程同 token 同 SKU → 只有 1 单，1 次 201 + 7 次重放，库存 10 → 9

test_stock_is_never_oversold
  库存 5、12 线程各买 1 → 成功 5、STOCK_NOT_ENOUGH 7
  stock 0、version 5、订单 5（没有负数，也没有少扣）

test_concurrent_cancel_restocks_only_once
  6 线程同时取消同一单 → 6 次都返回 CANCELLED，库存回到 10、券回到 UNUSED
```

两条保护的分工写清楚：

- **同 token 只一单**：唯一索引是最后防线，不是流程。查询命中就直接返回；
  两个都查不到时由 `uq_order_user_client_token` 挡下后来者，捕获冲突后在 `atomic` 外回查赢家的单
  （事务内读到的是自己的快照，查不到对方刚提交的行）。
- **取消只回补一次**：赢家由 `UPDATE ... WHERE status=PENDING` 的 rowcount 判定，
  只有 rowcount=1 的那次才回补库存、退券，副作用在同事务里；后来者读到 CANCELLED 直接返回。

### E5 前端手工清单（浏览器实测 2026-11-11）

| 步骤 | 结果 |
|---|---|
| 打开 `/products`（已登录） | 6 商品 + 3 张券；商品卡片整块可点进详情 |
| 点「领取」 | 剩余 49 → 48，按钮变「已领取」并禁用 |
| 点商品进入 `/products/4` | 黑色 ¥99 / 白色 ¥109、库存、数量、券下拉、备注都在；合计 ¥99.00 |
| 选「满 49 减 5」 | 优惠 -¥5.00，应付 ¥94.00 |
| 提交订单 | 跳 `/orders?order=OD…`，详情抽屉自动打开；支付截止 = 下单时间 + 15 分钟 |
| 取消（确认框） | 状态变「已取消」，取消按钮消失；库存 200 → 199 → 200，券回到「我的券」 |
| 刷新 `/orders` | 仍是登录态，订单列表与状态保持 |

截图：`..\assets\s3-orders.png`（订单列表 + 详情抽屉 + 已取消状态）。

顺手修掉的一处：Element Plus 默认是英文 locale，确认框按钮显示 `Cancel / OK`，与中文界面不一致；
在 `main.js` 传入 `zh-cn` 后变「取消 / 确定」。

### E6 本机检查

```text
pytest                          → 57 passed（新增 trade 25：规则 4 + 服务层 10 + 接口 8 + 并发 3）
ruff check / format --check      → 全过
python scripts/check_comments.py → 1.8%（上限 5%）
npm run lint / npm run build     → 0 warning；构建成功
```

构建时有一条 chunk > 500 kB 的体积告警：Element Plus 整包约 1.1 MB，按 plan §8 不做按需优化，先记着。
