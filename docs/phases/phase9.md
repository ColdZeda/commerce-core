# phase9 视觉与身份

> 二期第一阶段。目标：让陌生访客一眼看出这是个电商站，并能自己注册进来。
> 范围见 `plan.md` §11 与 §13，决策见 §13.3。

## 做了什么

### 主题

三版首页静态稿（清爽 / 深色 / 暖色）先给用户选，选定**暖色**（米白 #fbf7f1 + 陶土橙 #c2410c，圆角 16px）。
静态稿在 `C:\projects\commerce-core\.scratch\s9-mockups\`，不进仓库——它是一次性选型材料，不是产品资产。

落地方式：暖色只写成 `frontend/src/style.css` 的一组 CSS 变量，同时覆盖 Element Plus 的
`--el-color-primary` 系列。页面不写死颜色，改一处就换肤。

### 商品与分类

`Product` 增加三个字段（`description` 一期已有，本期开始真的用）：

| 字段 | 用途 |
|---|---|
| `category` | 六个分类之一，`TextChoices` 固定取值 |
| `cover` | 封面 SVG 的**路径**，如 `/img/products/kbd-87.svg` |
| `is_featured` | 首页"热销"；没有真实销量就不编造 |

`cover_url` 是 `URLField`，本项目不做上传、也不外链图片，改成只存路径的 `CharField` 并改名 `cover`。
同一张迁移里做 `RenameField` + `AlterField`，没有数据要保。

30 个商品、6 类 × 5，30 张 SVG 在 `frontend/public/img/products/`。线稿风格，每张 400×400，
描边 `#8a7358`，随前端一起打包，nginx/whitenoise 直接发静态文件。

`GET /products` 新增两个筛选：`category`（未知分类返回 400，不返回空列表）、`is_featured=1`。
`keyword` 一期就有，本期继续复用，没有新增搜索实现。

### 首页

`/` 从"重定向到商品列表"变成真首页：banner、六个分类入口、三张券、热销 8、新品 8、服务承诺、页脚。
商品总量只有 30 个，首页一次取回（`page_size=50`）再在本地分组，比"热销 / 新品 / 分类计数"各打一次接口简单。

首页楼层用四列（8 个正好两排），列表页用五列（每页 10 个正好两排）。列数不同是有意的：
首页看气质，列表看密度。

### 注册

`POST /auth/register`：用户名 + 密码 + 确认密码，成功直接返回与登录同结构的 `access/refresh/user`，
前端存完 token 就是登录态。口令强度用 Django 自带的 `AUTH_PASSWORD_VALIDATORS`（settings 里本来就有），
不另外造一套规则。重名判断忽略大小写，但唯一索引区分大小写——否则 `Bob` 和 `bob` 能同时注册、
登录时只有一个能用。

注册成功自动发「新客满 49 减 5」：复用 `claim_coupon`，券不存在或已领完时静默跳过，
**不能让发券失败把注册搞挂**。

### 页面

| 页面 | 变化 |
|---|---|
| `/` | 新增首页 |
| `/products` | 分类胶囊 + 排序 + 五列带封面卡片 + 分页 |
| `/products/:id` | 三栏：封面 / 规格与描述 / 结算（结算逻辑没动，只换版式） |
| `/login` | 左侧文案 + 右侧表单 |
| `/register` | 新增 |
| `/orders` | 只换外层壳，抽屉宽度 460 → 560（五列表格被切掉一列） |

`App.vue` 从"一个顶栏"变成完整外壳：工具条、搜索头、分类导航、页脚。
头部搜索框提交后跳 `/products?keyword=`，与一期列表接口的 `keyword` 参数对齐。

## 证据

```
$ .venv\Scripts\python -m pytest -q
133 passed                      # 一期 118 + 本期 15

$ .venv\Scripts\python -m ruff check . && ruff format --check .
All checks passed! / 94 files already formatted

$ python scripts/check_comments.py backend
注释行 63 / 代码行 3375，占比 1.8%（上限 5%） / OK

$ cd frontend && npm run lint && npm run build
eslint 无输出；vite build 成功（dist 1.11 MB js，全量引入 Element Plus）

$ python manage.py seed_demo
新增商品 24 个、补齐分类/封面 6 个、SKU 26 个、券 0 张；
当前商品 30 个、SKU 35 个、券 3 张
  键盘: 5 个 / 鼠标: 5 个 / 耳机: 5 个 / 显示器: 5 个 / 支架: 5 个 / 扩展坞: 5 个
```

`makemigrations --check` 无漂移。

本地联调走了一遍完整链路（截图在 `.scratch/s9-shots/`）：

1. `/register` 注册 `tryout-s9` → 跳到首页，顶栏显示用户名；
2. 首页「新客满 49 减 5」立刻变成**已领取**，`user_coupon` 里多一条；
3. 机械键盘 104 键 → 立即下单 → 订单详情抽屉显示待支付；
4. 模拟支付 → 已支付。

## 踩到的坑

- **SVG 没有 `width/height` 只有 `viewBox`**：作为 `<img>` 加载时浏览器按 150×150 算固有尺寸。
  卡片上用 `object-fit: contain` 兜住，但 banner 里图会显得很小——最后改成按商品挑图（banner 固定给键盘，
  和文案"从一块好键盘开始"对齐），而不是随便取前两个。
- **`stroke-width` 是 viewBox 单位**：同一套 64 单位图标放到 16px 的按钮里，实际描边只有 0.5px，几乎看不见。
  所以要按使用尺寸分别给 stroke-width，不能在根元素写一个值了事。
- **注释检查器把 `# ---- 键盘 ----` 判成分区横幅**：`seed_demo` 里按分类分段的注释被 `check_comments.py`
  拦下（§6 第 5 条禁止分区横幅）。分类已经写在每条数据的 `category` 字段里，注释是重复信息，直接删掉。
- **`py` 输出的中文在 PowerShell 里是乱码**：`Get-Content` 按 ANSI 解码会毁掉内容，
  改文件一律走 `read`/`edit`，只有纯粹的机械替换才用脚本。

## 与计划的偏差

| 项 | 计划 | 实际 | 为什么 |
|---|---|---|---|
| 列表筛选 | S11 做"搜索/排序筛选栏" | `category`、`is_featured` 的**接口参数**在 S9 就加了 | 首页分类入口、导航、热销位都要跳带筛选的列表，没有参数这些链接就是死的。S11 补的是筛选栏 UI 与排序，不是参数 |
| 首页排序 | 热销 8 + 新品 8 | 一致 | —— |
| 注册限流 | S13 | 本期没做 | 按阶段顺序，S13 统一接限流 |
| `is_featured` 的 seed 行为 | —— | 只在新建时写入，重跑不覆盖 | 它与价格/库存一样属于"人调过的值"，seed 只补缺 |

## 未做

- 购物车（S10）：卡片右下角的「+」现在就是打开详情页，不是加购；
- 地址与物流（S11）、评论（S12）、后台与看板（S13）、退款（S14）；
- README 的界面段落：等上线后从线上环境重新截图再改，本地开发环境的截图不作为最终图。
