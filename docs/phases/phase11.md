# phase11 地址与搜索

> 二期第三阶段。目标：下单带收货地址并快照，列表页有真正的搜索/排序栏，订单页能看见进度。

## 做了什么

### 地址

新增 `address` app，一张表：

| 字段 | 说明 |
|---|---|
| `receiver` / `phone` | 收件人与手机号 |
| `region` | 省市区**一段文本**，如"广东省 深圳市 南山区" |
| `detail` | 街道门牌 |
| `is_default` | 默认地址 |

不做行政区级联、不引入行政区数据表——演示里没有物流，级联只增加维护面。
手机号只校验"7 到 15 位数字"，允许带 `-` 和空格，规范化后入库。

默认地址的规则：第一条自动默认；设为默认"先全清再置位"，保证同一用户最多一条；
删掉默认地址后把剩下最新的一条顶上来，避免用户以为有默认地址却选不到。

接口：`GET/POST /addresses`、`PATCH/DELETE /addresses/{id}`，只操作本人的地址，越权 404。

### 下单快照

`Order.address_snapshot` 是 `JSONField`，`POST /orders` 接受 `address_id`，
下单瞬间把 `{receiver, phone, region, detail}` 拍进订单。
之后地址被改、被删，订单上的收货信息都不变（`test_snapshot_survives_address_edit_and_delete`）。

`address_id` 在接口层是**可选**的：一期 152 个用例里大量 `POST /orders` 不带地址，
强制必填等于把测试夹具全改一遍，收益只是"接口更严格"。前端的两个下单入口都强制选地址，
所以线上不会出现没有地址的单；接口留这个口子是为了不破坏既有契约。

### 前端

| 位置 | 变化 |
|---|---|
| `/addresses` | 新页面：列表、新增/编辑弹窗、设为默认、删除 |
| `AddressPicker` | 一个组件，购物车与详情页共用；进页面自动落到默认地址 |
| 购物车 | 地址选择放在结算区，没选地址时「去结算」禁用 |
| 商品详情 | 「立即购买」也会带地址，两个下单入口口径一致 |
| 列表页 | 独立搜索框 + 排序 + 分类胶囊，搜索词进 URL，可直接分享 |
| 订单详情 | 多一块收货地址；新增「进度」时间线 |

时间线只画**真实发生过的事**：下单、已支付（有 `paid_at` 才画）、已取消、超时关闭（有 `closed_at` 才画），
最后一条固定是「物流：演示项目未接入」。没有编造"已发货"节点——这个项目确实没有物流。

`status_name` 是本期给订单列表接口加的字段（`pending/paid/cancelled/closed`），
前端按名字判断状态，不去猜 `status` 的 0/1/2/3。

## 证据

```
$ .venv\Scripts\python -m pytest -q
176 passed                # 一期 118 + S9 15 + S10 21 + S11 15 + 勾选/部分结算 7

$ ruff check . && ruff format --check .
All checks passed! / 114 files already formatted

$ python scripts/check_comments.py backend
注释行 81 / 代码行 4123，占比 1.9%（上限 5%） / OK

$ cd frontend && npm run lint && npm run build
eslint 无输出；vite build 成功
```

本地联调（截图在 `.scratch/s9-shots/`）：

1. `/addresses` 新增一条地址 → 自动成为默认，卡片带「默认」标；
2. `/cart` 结算区直接落到这条地址，勾选两件后去结算；
3. 订单详情出现「收货地址」与「进度」，支付后再看，时间线多一个「已支付」节点；
4. 列表页带 `?keyword=键盘` 打开，筛选栏回填搜索词，结果 5 件。

## 上线

| 项 | 结果 |
|---|---|
| 合并 | `main` 收到 `24a870c`，推 GitHub 与 Gitee；CI 四段全绿 |
| 部署 | `.current_tag` 从 `65094bd` 变 `24a870c`，6 个容器全 Up，api healthy |
| 迁移 | `cart.0002`、`address.0001`、`trade.0002` 由 `deploy.sh` 自动执行 |
| 接口 | 未登录访问 `/addresses`、`/cart/items` 均 401，说明路由与新表都生效 |
| 线上联调 | `demo` 账号：新增一条地址（自动默认）→ 加购两件 → 购物车显示地址与「已选 2 件 ¥688」 |

README §2 的购物车截图换成线上实拍（带勾选与地址栏）。

## 流程偏差

这次的两个提交（购物车逐行勾选、S11）**直接落在 `main` 上**，没有走 `phase2` 分支再合并。
原因是我在 S10 收尾时切到了 `main` 就没切回来，后面两次 `git add/commit` 都提交在当前分支。
代码内容不受影响，但 `main` 少了两个 `--no-ff` 合并点，`git log --first-parent` 看不出阶段边界。
之后继续在 `phase2` 上开发，收尾时把 `phase2` 快进到 `main` 保持一致。

## 踩到的坑

- **Django 开发服务器带 `--noreload` 不会加载新 app**：新增 `address` 之后页面一直 404，
  查了半天前端，最后发现是进程还是加 app 之前那个。新增 app 或改 URL 根表后必须重启。
- **`.addr-title span` 会把「默认」标签也染成灰色**：`.addr-tag` 是 span，被更具体的后代选择器盖住，
  改成 `.addr-title .addr-tag` 提权才生效。

## 未做

- 地址库的行政区级联、地址自动识别、手机号归属地校验
- 真实物流（时间线最后一条是占位）
- 评论（S12）、后台与看板（S13）、退款（S14）
