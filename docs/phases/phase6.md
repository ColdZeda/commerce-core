# phase6 — S6 模拟支付

> 阶段号与 `docs/plan.md` §11 的 S6 对应。阶段结束封口，不再追加；新内容进 phase7。

## 目标

把订单从"待支付"推到"已支付"，并且让两条入口（登录用户的 mock 支付、匿名的第三方回调）走**同一个**
service。要证明的是：重复支付/重复回调只生效一次，`PAID` 之后取消被拒，伪造或过期的回调进不来，
已关闭/已取消的订单不会被回调改回已支付。

## 范围

- `trade/rules.py`：加 `PENDING → PAID` 一行（副作用只有 `paid_at`，不回补库存、不退券）
- `trade/payments.py`：HMAC-SHA256 签名与校验（`order_no|trade_no|amount|timestamp`）、时间窗判断
- `trade/services.py`：`mark_order_paid(order_no, amount, trade_no)`，两条入口共用
- 接口：
  - `POST /orders/{order_no}/pay`：登录 + `ENABLE_MOCK_PAY` 开关；`PENDING→PAID`，已支付幂等成功
  - `POST /payments/callback`：匿名 + HMAC；已支付返回 `200 + idempotent: true`；
    `CLOSED`/`CANCELLED` 返回 409 `ORDER_NOT_PAYABLE`
- 前端：订单页与详情抽屉加「模拟支付」按钮（plan §8 的第四个动作，S3 时接口还没做）
- 配置：`ENABLE_MOCK_PAY`、`PAY_CALLBACK_SECRET`、`PAY_CALLBACK_WINDOW_SECONDS`

## 明确不做

- 不接真实支付渠道、不做退款/对账（plan §2.5 明确不做）
- 不建支付流水表：mock 的 `trade_no` 不落库，只用于签名与日志（plan §4.2 备注）
- 不启用 simplejwt 的 blacklist，不做服务端强制下线
- 不做支付后的库存/券变更：`PAID` 是终态，正确业务是退款流程，本项目不做

## 门槛

- [x] `/pay` 与 `/callback` 都只通过 `mark_order_paid` 改状态，没有第二套写法
- [x] 重复支付 / 重复回调只生效一次：第二次返回 200 且 `paid_at` 不变
- [x] `PAID` 后取消被拒（409），库存不回补、券不退
- [x] 签名错、时间戳超窗、金额不符分别被拒，且不产生的状态变更
- [x] `CLOSED`/`CANCELLED` 订单的回调返回 409，状态不被改回
- [x] `ENABLE_MOCK_PAY=false` 时 `/pay` 返回 403，回调不受影响
- [x] `pytest` / `ruff` / `check_comments` / `check_lock` / `npm run lint` 全过

## 实施顺序

1. `phase6.md`（本文件）
2. `rules.py` 加 PAID；`payments.py` 签名工具 + `mark_order_paid`
3. 两个接口 + 序列化 + 错误码
4. 测试（含并发重复回调）
5. 前端「模拟支付」按钮
6. 证据回填、`STATUS.md`、推送

## 实现级决定（先记理由再实施，AGENTS §1.3）

1. **签名串固定为 `order_no|trade_no|amount|timestamp`，amount 用两位小数字符串**。
   金额参与签名才能挡住"改金额"的回调；格式固定两位小数，避免 `94` 与 `94.00` 两种写法导致签名对不上。
2. **时间窗 ±300 秒**（`PAY_CALLBACK_WINDOW_SECONDS`），比 JWT 的 15 分钟短：回调是一次性动作，
   窗口越短重放价值越低；窗口内重放由"已支付幂等"兜住。
3. **签名校验用 `hmac.compare_digest`**，不用 `==`：避免比较耗时泄露前缀。
4. **`PAY_CALLBACK_SECRET` 独立于 `DJANGO_SECRET_KEY`**，默认回落到 `SECRET_KEY` 并在文档写清；
   生产可以单独换，不用因此轮换 JWT 签名密钥。
5. **`trade_no` 不落库**。plan §4.2 已定案"mock 的 trade_no 不强制建支付流水表"；本阶段只把它放进
   日志与签名，避免为演示引入第七张表。
6. **`/pay` 用请求体里的金额吗？不用**。服务端按订单 `pay_amount` 自己算，客户端传的金额只用于回调验签；
   `/pay` 的入参只有可选的 `trade_no`，没有金额字段。
7. **回调是匿名接口**，`authentication_classes = []`：带 Bearer 反而会让"第三方回调"这件事变模糊；
   身份由 HMAC 证明，不是由 JWT 证明。
8. **`PAID` 的副作用是 `paid_at` 一个字段**，写在同一条 `UPDATE` 里，不进 `EFFECTS` 注册表：
   `EFFECTS` 是给"跨表副作用"用的（回补库存、退券），同一行的字段更新不该绕一圈。

## 证据

### E1 状态机与 service（14 个用例）

```text
规则表          → PENDING→PAID 的 effects 为空元组（支付没有跨表副作用）
mark_order_paid → 待支付 → 已支付，paid_at 落库
                  已支付再调 → 返回 (订单, True)，paid_at 不变
                  已关闭再调 → 409 ORDER_NOT_PAYABLE
                  金额不符   → 409 PAY_AMOUNT_MISMATCH，状态不变
                  不存在     → 404 NOT_FOUND
支付不退券      → 用券下单后支付，券仍是 USED（退款才该退券，本项目不做）
```

### E2 两个入口

```text
POST /orders/{no}/pay  未登录 → 401
                       已登录 → 200，status=1、paid_at 有值
                       再点一次 → 200 + X-Idempotent-Replay: 1
                       ENABLE_MOCK_PAY=false → 403 PAY_NOT_ENABLED，订单仍 PENDING
                       已关闭的订单 → 409 ORDER_NOT_PAYABLE

POST /payments/callback 匿名（无 JWT）+ 正确签名 → 200 {idempotent: false}，订单 PAID
                        同一份 payload 再来 → 200 {idempotent: true}，paid_at 不变
                        订单不存在 → 404
```

### E3 回调校验（错在哪一步就停在哪一步）

```text
签名被改一个字符   → 401 PAY_SIGN_INVALID，订单仍 PENDING
时间戳超 300 秒    → 401 PAY_SIGN_INVALID（先判时间窗，再判签名）
金额与应付不符     → 409 PAY_AMOUNT_MISMATCH（签名本身有效，签名串里带金额）
已关闭订单         → 409 ORDER_NOT_PAYABLE，状态仍是 CLOSED
```

签名串固定 `order_no|trade_no|amount|timestamp`，金额按两位小数字符串参与；比较用 `hmac.compare_digest`。

### E4 并发重复回调（6 线程）

```text
6 个线程同时 mark_order_paid 同一单
→ 恰好 1 次 already=False、5 次 already=True
→ 订单 PAID，paid_at 只写一次
```

### E5 前端手工清单（浏览器实测）

| 步骤 | 结果 |
|---|---|
| 商品详情下单 | 跳 `/orders?order=…`，抽屉里出现「模拟支付 / 取消订单」 |
| 点「模拟支付」 | 中文确认框「只把订单标记为已支付，不会真的扣款」 |
| 确定 | 列表与抽屉同时变「已支付」，支付/取消按钮消失 |
| 数据库 | `status=1`、`paid_at=2026-11-11 05:32:26Z`、`pay_amount=99.00` |

### E6 本机检查

```text
pytest                          → 99 passed（新增 14：支付 13 + 规则 1）
ruff check / format --check      → 全过
python scripts/check_comments.py → 1.9%（上限 5%）
python scripts/check_lock.py     → lock=36 installed=36（本阶段没加依赖）
npm run lint / npm run build     → 0 warning；构建成功
```
