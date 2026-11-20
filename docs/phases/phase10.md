# phase10 购物车

> 二期第二阶段。目标：把"买一件东西"从详情页直买，扩成加购 → 改量 → 结算的标准流程。
> 范围见 `plan.md` §11，决策见 `plan-changes.md` D-011。

## 决策（用户拍板）

商品详情页**并列两个按钮**：「加入购物车」与「立即购买」。
`POST /orders` 因此接受两种来源，二者互斥：

```jsonc
// 立即购买
{ "items": [{ "sku_id": 22, "qty": 1 }], "client_token": "..." }

// 购物车结算
{ "from_cart": true, "client_token": "..." }
```

两个都传返回 400；都不传也返回 400。

## 后端

新增 `cart` app。

| 项 | 内容 |
|---|---|
| 表 | `cart_item`：`user` + `sku` 唯一约束、`qty >= 1` 的 CHECK、**不存价格** |
| 接口 | `GET/POST /cart/items`、`PATCH/DELETE /cart/items/{id}` |
| 返回 | 三个写接口都回整车快照 `{items, total_qty, total_amount}`，前端整体替换不做增量合并 |
| 可售标记 | 每行带 `available`：SKU 下架、商品下架、或数量超库存时为 `false`，前端据此禁用结算 |

**为什么购物车不存价格**：价格只有一个来源（`SKU.price`），存进车里就要处理"加购后改价"的
同步问题，而演示里没有任何理由让车里的价格和商品页不一致。

并发处理：同一 SKU 首次并发加购会撞唯一索引，捕获 `IntegrityError` 后重试一次走累加分支；
已有行用 `select_for_update` 锁住再算数量，超库存时抛错让整个 `atomic` 回滚——
所以"加到超出库存"不会留下半截结果，测试里专门验了这一点。

**结算清车的时机**：`create_order` 成功之后、且**不是重放**时才清车。
重放说明这批行上次已经下过单、当时就清过，再清一次会误删重放之后新加的商品
（`test_replay_does_not_clear_items_added_afterwards` 守这条）。
下单失败时车保留，用户可以改量重试。

## 前端

| 位置 | 变化 |
|---|---|
| 顶栏 | 「购物车」按钮带件数角标，登录态变化时重新拉取整车；退出即清空 |
| 详情页 | 「加入购物车」+「立即购买」并列，加购后角标立即变 |
| `/cart` | 新页面：清单、`el-input-number` 改量、删除、合计、去结算 |
| 结算 | 点「去结算」发 `from_cart: true`，成功后清车并跳订单页 |

购物车状态放在 Pinia 的 `cart` store 里，因为顶栏角标、详情页加购、购物车页三处都要用同一份数据。

## 证据

```
$ .venv\Scripts\python -m pytest -q
152 passed                    # 一期 118 + S9 15 + 购物车 14 + 从车结算 5

$ ruff check . && ruff format --check .
All checks passed! / 104 files already formatted

$ python scripts/check_comments.py backend
注释行 71 / 代码行 3725，占比 1.9%（上限 5%） / OK

$ cd frontend && npm run lint && npm run build
eslint 无输出；vite build 成功
```

本地联调（截图在 `.scratch/s9-shots/`）：

1. 详情页点「加入购物车」→ 顶栏角标 1；
2. 再加一件别的商品 → 角标 2，购物车两行、合计 ¥688；
3. 数量 +1 → 小计与合计同步变 ¥718，角标变 3；
4. 去结算 → 订单页出现两行明细、待支付、金额 ¥688；
5. 再进购物车 → 空的，角标消失。

## 踩到的坑

- **`.cart-summary span` 把 Element Plus 按钮里的文字也染成深色**：按钮内部就是 `<span>`，
  `.cart-summary span` 直接命中，橙底上出现深棕色文字。改成给自绘的那行加 `.cart-total`，
  不去碰别人的 DOM 结构。
- **首次加购的并发路径不能就地重试**：`IntegrityError` 在 `atomic` 块内会让事务标记为
  需要回滚，接着查询会抛 `TransactionManagementError`。必须等这一块结束，再开一个新的
  `atomic` 回查。

## 未做

- 购物车跨设备同步（现在就是服务端存，天然同步，没有额外做）
- 选中商品结算（整车一起结算，不做逐行勾选）
- 地址与物流（S11）、评论（S12）、后台与看板（S13）、退款（S14）
