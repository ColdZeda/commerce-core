# phase12 评论

> 二期第四阶段。目标：买过的人能给商品打分，商品页能看见评分与评价。

## 做了什么

### 表

新增 `review` app，一张表：

| 字段 | 说明 |
|---|---|
| `user` | 谁评的（`PROTECT`，删用户不删评价） |
| `order_item` | **一对一**到订单明细——这就是"一条明细只能评一次"的硬约束 |
| `product` | 冗余存商品：商品页按它查，不必每页都从明细绕到 SKU |
| `rating` | 1–5，带 CHECK |
| `content` | 最多 500 字，可空 |

`order_item` 用 `OneToOneField` 而不是"普通外键 + 应用层判重"：唯一性交给数据库，
并发下也不会出现两条。服务层仍先查一次是为了给出**明确的 409**，而不是让用户看到 `IntegrityError`。

### 接口

| 接口 | 鉴权 | 说明 |
|---|---|---|
| `GET /products/{id}/reviews` | 匿名 | 分页；额外带 `summary: {count, average}` |
| `POST /orders/{order_no}/review` | 登录 | 只对本人**已支付**订单；一次可提交多条明细 |

写评价的校验顺序：订单归属（404）→ 订单状态（409 `REVIEW_ORDER_NOT_PAID`）→
明细归属（404）→ 已评过（409 `REVIEW_ALREADY_EXISTS`）→ 商品还在（409 `REVIEW_PRODUCT_GONE`）。

**一次提交多条，整批原子**：`bulk_create` 放在一个事务里，一条不合法整批都不落库，
不留"评了两个失败一个"的半截状态。计划里写的是 `POST /orders/{order_no}/review`（单数），
这里是**同一个路径收一个数组**——路径不变，只是体是列表。

商品详情接口新增 `review_count` 与 `rating_average`：在同一个查询里 `annotate`，
详情页"查询数恒为 2"的契约没有被破坏。

用户名在公开接口里做掩码（`buyer` → `b***`）：免登录接口不该把用户名整串吐出去。

### 前端

| 位置 | 变化 |
|---|---|
| 商品详情 | 头部元信息里显示星级与条数；正文底部新增「评价」区，5 条一页，可继续加载 |
| 订单详情 | 已支付且有未评明细时出现「评价商品（N）」；弹窗里每行一个星级 + 一个文本框，一次提交 |
| 订单明细 | 接口多一个 `reviewed`，前端据此决定还显示不显示评价入口 |

评完再打开订单，按钮就消失了——因为所有明细的 `reviewed` 都变成 true。

## 证据

```
$ .venv\Scripts\python -m pytest -q
193 passed                # 一期 118 + S9 15 + S10 21 + S11 15 + 地址必填 3 + 评论 18 + 其他

$ ruff check . && ruff format --check .
All checks passed! / 123 files already formatted

$ python scripts/check_comments.py backend
注释行 93 / 代码行 4459，占比 2.0%（上限 5%） / OK

$ cd frontend && npm run lint && npm run build
eslint 无输出；vite build 成功
```

本地联调（截图在 `.scratch/s9-shots/`）：

1. 已支付订单 `OD…40724` 的详情里出现「评价商品（1）」；
2. 弹窗给「茶轴」打 5 星并写一句评价，提交成功；
3. 再打开同一单，按钮消失；
4. 商品页头部出现 5 星与「1 条」，底部评价区出现 `t***  5 星  手感很稳……`。

## 踩到的坑

- **详情页元信息被评价撑爆**：加了星级之后 `.detail-meta` 里四段挤在一行，
  「分类 · 键盘」被拆成两行。加 `flex-wrap: wrap` 并给每段 `white-space: nowrap`，
  挤不下就整段换行。
- **`hasattr(obj, "review")` 配 `select_related` 才不额外查库**：明细的 `reviewed`
  是反查一对一，不 `select_related("review")` 就是每条明细一次查询。

## 未做

- 评价的编辑与删除、"有用"投票、图片评价
- 按星级筛选评价、评价置顶
- 后台与看板（S13）、退款（S14）
