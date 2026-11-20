# phase13 运营与看板

> 二期第五阶段。目标：账平能一眼看出、后台能管商品但改不了状态、一条命令能把站跑起来。

## 做了什么

### 限流

`common/ratelimit.py`，Redis 固定窗口，`INCR` + 首次数时设过期。

| 接口 | 限制 |
|---|---|
| `POST /auth/register` | 10 次 / 小时 / IP |
| `POST /auth/login` | 30 次 / 分钟 / IP，另加 5 次 / 分钟 / 用户名 |

登录两道都要：IP 挡撞库，用户名挡"换 IP 继续猜同一个账号"。用户名比较前统一小写，
否则换个大小写就能绕过。超限返回 429 + `Retry-After`，错误体沿用统一格式（`TOO_MANY_REQUESTS`）。

**Redis 故障时放行**：登录和注册是演示站唯一的人口，缓存挂掉应该是"能用但不设防"，
而不是"整站没人能注册"。异常只记一条 warning。

计数用 Redis 的 6 号库，和 Celery 的 broker（0 号库）分开，避免键名混在一起。
测试里 `RATELIMIT_ENABLED = False`（几百个用例都在打登录注册，开着会互相干扰），
限流本身由 `accounts/tests/test_ratelimit.py` 9 条用例打开开关单独验。

### 后台

| 对象 | 权限 |
|---|---|
| 商品 | 可编辑；封面缩略图、分类/热销/上下架筛选，热销与上下架可在列表页直接改 |
| 订单、订单明细 | **只读** |
| 券、用户券 | **只读** |

只读用 `has_add/change/delete_permission` 全部返回 False。理由写在 plan §13.3：
状态只能由接口那条条件更新推进，后台一旦能改就是绕过状态机——回补、退券、幂等全都会失真。

商品封面用 `<img src="cover">` 直接引站内路径，因为封面本来就随前端打包。

### 后台静态

whitenoise + `collectstatic` 打进镜像：

- `Dockerfile` 构建期跑一次 `collectstatic`（给个占位 `DJANGO_SECRET_KEY`，只为让 settings 能 import）
- 中间件紧跟在 `SecurityMiddleware` 之后
- nginx 加 `location /static/ { proxy_pass http://api:8000; }`

`/admin/` 本身仍受 C1 的 IP 限制（公网 404），但 `/static/` 是公开的——它只有 admin 的 CSS/JS，
没有业务数据。

### 对账看板

`GET /api/v1/audit` 免登录只读，前端 `/audit` 一个表格页。

按 SKU 列：初始 / 已售 / 回补 / 账面 / 明细合计 / 差额 / 状态。

```
账面 = 初始 - 已售                  （已售只算待支付 + 已支付）
已售 + 回补 = 明细合计               （取消 + 超时关闭的都回补过）
```

两条恒等式都成立才算"平"。看板还会给券的发放/使用/总量和订单各状态计数。

**为此加了 `SKU.initial_stock`**：没有基线的话，"账面该是多少"只能反推，看板就成了摆设。
基线在 SKU 第一次落库时记下，之后改库存不动它——所以**绕过接口改库存会让看板变红**，
这正是想要的信号（`test_manual_stock_edit_shows_up_as_unbalanced` 守这条）。
历史数据由 `catalog/0004` 回填：`初始 = 当前库存 + 净已售`。

看板不含用户名、手机号、地址，只有数量（`test_report_does_not_leak_user_data` 守这条）。

### 一键脚本

`scripts/dev-up.ps1`：

```
检查 docker/npm → 起 MySQL+Redis → 等 MySQL healthy → 装后端依赖（缺才装）
→ 迁移 → seed_demo → 装前端依赖（缺才装）→ 起 :8000 与 :5173
→ 等两边都通 → 打印地址 → Ctrl+C 一起停
```

`-NoServers` 只准备环境不起服务，`-SkipSeed` 跳过种子数据。
Vite 用 `--host 127.0.0.1`，不把开发端口暴露到局域网。

## 证据

```
$ .venv\Scripts\python -m pytest
215 passed

$ ruff check . && ruff format --check .
All checks passed! / 134 files already formatted

$ python scripts/check_comments.py backend
注释行 113 / 代码行 4870，占比 2.3%（上限 5%） / OK

$ cd frontend && npm run lint && npm run build
eslint 无输出；vite build 成功

$ powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1
==> 检查 Docker 与 Node      docker / npm 都在
==> 启动 MySQL 与 Redis       容器已启动
==> 等待 MySQL 就绪          MySQL healthy
==> 执行数据库迁移            迁移完成
==> 写入演示数据              当前商品 30 个、SKU 35 个、券 3 张
==> 启动后端 :8000 与前端 :5173
  站点   http://127.0.0.1:5173
```

线上验证（`612dcdb`）：

| 项 | 结果 |
|---|---|
| `/api/v1/audit` | 200，35 个 SKU、`unbalanced=0`，恒等式全部成立 |
| `/static/admin/css/base.css` | 200（whitenoise 正常发后台静态） |
| `/admin/`（公网） | 404（C1 未破） |
| `/admin/`（服务器内 127.0.0.1） | 302 → 登录页 200（隧道能进后台） |
| 登录限流 | 同一用户名连续 7 次错误口令：5 次 401 后第 6、7 次 429 |

## 上线

线上验证（`612dcdb` / `a8814eb` / `e642b2b` 三次部署，CI 全绿）：

| 项 | 结果 |
|---|---|
| `/api/v1/audit` | 200，35 个 SKU、`unbalanced=0`，恒等式全部成立 |
| `/static/admin/css/base.css` | 200（whitenoise 正常发后台静态） |
| `/admin/`（公网） | 404（C1 未破） |
| `/admin/`（服务器内 127.0.0.1） | 302 → 登录页 200（隧道能进后台） |
| 登录限流 | 同一用户名连续 7 次错误口令：5 次 401 后第 6、7 次 429 |

补做的两件事（`e642b2b`）：`create_demo_user --staff`（已存在的普通号可只补权限、不动口令），
以及把"订单/券在 admin 只能看不能改"写成用例（POST 一律 403）。
这两条是 §13.3 承诺过但第一版没验的，补上后 S13 才算收口。

## 踩到的坑

- **`.ps1` 没有 BOM，PowerShell 5.1 按 ANSI 读**：中文全变成乱码，还连带把花括号判成语法错误。
  `.ps1` 必须存成 UTF-8 **带 BOM**（Python/JS/Markdown 不要 BOM，两边规矩相反）。
- **`initial_stock` 的回填不能只依赖 `catalog` 的迁移链**：它要读 `order_item`，
  得显式依赖 `trade.0002`，否则全新库上会先跑回填再建订单表。跨 app 依赖不影响 catalog 的唯一叶子节点。
- **对账公式一开始写错了**：写成 `初始 - 已售 + 回补`，而"已售"本身已经排除了取消/关闭的明细，
  再加一次回补等于把退回的部分重复算了一遍。正确的是 `初始 - 已售`，回补只作展示列。
- **直接改订单状态不会触发回补**：测试里用 `Order.objects.update(status=CLOSED)` 造已关闭订单，
  库存没动、账自然不平。要用 `close_order()` 走真实路径。

## 未做

- 全站限流、IP 黑名单、验证码
- 看板的历史趋势与导出
- 退款（S14）
