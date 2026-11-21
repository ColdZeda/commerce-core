# phase14 退款（二期收官）

> 二期第六阶段，也是最后一个阶段。目标：已支付的订单能退，退款之后对账看板仍然平。

## 做了什么

### 状态机只加了一行

`trade/rules.py` 多一条迁移，副作用直接复用取消/关单那两条：

```python
Transition(source=PAID, target=REFUNDED, effects=(RESTOCK, RETURN_COUPON))
```

`_apply_transition` 的执行方式一行没改：仍是 `UPDATE ... WHERE pk=? AND status=?`，
只有 rowcount=1 的赢家才跑副作用。改的是一处**取规则的方式**：

- 之前：固定按 `RULES[(PENDING, target)]` 查，隐含假设"只有待支付会迁移"；PAID 的订单走到这里直接 KeyError。
- 现在：source 取订单当前状态，查不到规则就返回 `False`，由各 service 决定报 404 还是 409。
  "现在不能这么迁"成为规则表的结论，而不是每个 service 各写一遍 if（见 `plan-changes.md` D-015）。

加了两列：`refunded_at`（结构化时间，前端时间线用）与 `refund_reason`（与 `cancel_reason` 分开）。

### 接口

`POST /api/v1/orders/{order_no}/refund`，登录，body `{"reason": "选填"}`。

| 情况 | 返回 |
|---|---|
| 他人订单 / 不存在 | 404（两者不区分，单号不能当探测手段） |
| 待支付、已取消、已关闭 | 409 `ORDER_STATUS_INVALID` |
| 已退款 | 409 `ORDER_ALREADY_REFUNDED` |
| 成功 | 200 + 订单详情（与取消同形） |

重复退款给 409 而不是幂等 200：钱的动作重复请求要能被看见。列表也多一个 `?status=refunded`。

### 对账看板

`RETURNED` 加上 `REFUNDED`，订单计数多一个 `refunded`。**这一处最容易漏**：
退款把量从"已售"挪到"回补"，漏了的话两条恒等式同时不成立，线上立刻变红。

### 前端

- 订单页多一个「已退款」页签，状态标签用红色（与已关闭的灰色区分开）
- 已支付的行上出现「退款」，详情抽屉里是「申请退款」，弹一个可填原因的输入框
- 详情多出退款时间与退款原因，进度时间线多一个节点「已退款，库存与券已退回」
- 看板的回补口径改成"取消 + 关闭 + 退款"，订单计数多一格

### 演示订单

补上计划 §13.5 一直欠着的 `seed_demo_orders`：五个固定单号 `ODDEMO0001`–`ODDEMO0005`，
覆盖待支付/已支付/已取消/已关闭/已退款，另加两条评价。全部走真实 service，跑完自检对账，
不平就整批回滚。重跑按单号跳过，不重复消耗库存（见 `plan-changes.md` D-016）。

## 证据

```
$ .venv\Scripts\python -m pytest
232 passed

$ ruff check . && ruff format --check .
All checks passed! / 140 files already formatted

$ python scripts/check_comments.py backend
注释行 126 / 代码行 5268，占比 2.3%（上限 5%）

$ cd frontend && npm run lint && npm run build
eslint 无输出；vite build 成功
```

本机 HTTP 走一遍（runserver + 迁移后的开发库）：

```
register  -> rf-smoke-164536
address   -> 4
sku       -> 50 千兆 stock=160
order     -> OD20261121084537476538 status=pending pay=79.00
pay       -> status=paid
refund    -> status=4/refunded/已退款 refunded_at=2026-11-21T16:45:37+08:00 reason=smoke test
detail    -> refunded items=1
second refund -> 409 {"code":"ORDER_ALREADY_REFUNDED","message":"订单已经退过款"}
refund pending -> 409 {"code":"ORDER_STATUS_INVALID","message":"只有已支付的订单可以退款"}
audit     -> unbalanced=0 balanced=True refundedOrders=2 restocked_total=14
stock     -> before=160 after=159
```

最后一行 `-1` 是因为紧接着又下了一张待支付订单，不是退款没补回去。

`seed_demo_orders` 在开发库上跑两遍：

```
对账：35 个 SKU，unbalanced=0
新增演示订单 5 个、评价 2 条；当前订单 25 个、评价 3 条
--- 再跑 ---
对账：35 个 SKU，unbalanced=0
新增演示订单 0 个、评价 0 条；当前订单 25 个、评价 3 条
```

页面证据（1440×900）：订单抽屉里状态「已退款」、退款时间/原因、时间线第三个节点；
看板横幅"账是平的"，已退款 3 单、回补 15 件。

## 上线

合回 main：`7e99600`（分支）→ merge `5459cc9`。第一次 CI 在「登录 ACR」这一步失败（login 报错，
test/lint 都是绿的），空提交 `b33ca39` 重试后 lint / test / build & push / deploy 全绿；
线上 `current_tag` = `b33ca39`，`previous_tag` = `e61dfff`。

| 项 | 结果 |
|---|---|
| `/api/v1/health` | 200，`db: true`、`redis: true` |
| 迁移 | `trade.0003_order_refund_fields` 由 `deploy.sh` 在 `up -d` 之前跑完 |
| 容器 | 6 个 Up，api healthy |
| `seed_demo_orders`（线上跑一次） | 新增演示订单 5 个、评价 2 条；自检 `unbalanced=0` |
| 页面退款（线上新注册的访客账号） | 下单 → 模拟支付 → 退款全部成功，详情显示已退款、退款时间与原因 |
| 退款后 `/audit` | 35 个 SKU，`unbalanced=0`；`refunded=2`，`NET-GBE` 库存回到 160 |

README 按 `plan.md` §13.6 做了结构性重写：首屏改成"能证明什么 + 怎么点一遍"，
补上退款截图与 `seed_demo_orders`，接口表加到 26 条，故障记录加了"回补口径漏掉退款"这一条。

## 踩到的坑

- **执行器硬编码了 source**：`_apply_transition` 一直是 `RULES[(PENDING, target)]`，
  第一期只有"待支付出发"的迁移所以没暴露；退款一接上来，PAID 的订单会直接 KeyError。
- **对账的 `RETURNED` 漏加就是线上事故**：退款回补的库存算不进"回补"，
  `已售 + 回补 == 明细合计` 立刻不成立。S14 清单里专门列了这一条。
- **ruff E501**：命令里两条长行超 110 字符，`ruff format` 会拆行，先格式化再跑检查。
- **ESLint `no-useless-assignment`**：`let reason = ''` 的初值在后来的分支里永远用不上，
  改成 `let reason` 由 `try` 里赋值。
- **RR 下用普通 SELECT 判"退没退过"会判错**：条件更新看到的是最新提交，失败分支里
  `refresh_from_db()` 读到的却可能是事务开始时的快照，于是并发第二次退款会报"状态不对"而不是
  "已经退过"。失败分支改用 `select_for_update()` 的当前读，错误码才稳定（并发用例连跑 5 次验过）。

## 未做

- 部分退款、按商品退、退款审核流（演示站直接退）
- 退货地址、物流回传、真实资金流
- 退款后已写的评价不删：评价记录的是"买过并用过"，与订单是否退款无关
