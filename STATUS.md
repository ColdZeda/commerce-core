# STATUS

> 更新于 2026-11-21（S13 已上线；S14 待开工）。滚动覆盖，不追加历史。目标：10 秒读完。

## 现在在哪

**一期 S0–S8 已交付并封口**：业务闭环在公网跑通，CI/CD 与回滚演练过，
外部独立审查 10 项全部修完并终审通过（审查对象 `4ec7f93`）。

**二期 S9–S13 已全部上线**：视觉、购物车（含逐行勾选）、地址与快照、评论、限流 / 后台 / 看板 / 一键脚本。
**只剩 S14 退款**。

- 公网：`http://120.24.67.82:8080`（无域名无 HTTPS）
- 线上版本：`a8814eb`（`.current_tag`）
- 线上数据：30 个商品（6 类 × 5，都有图有详情）、35 个 SKU、3 张券、1 条地址、1 条评价
- **对账看板线上全平**：35 个 SKU，`unbalanced=0`
- 服务器 6 个容器：api(healthy) / web / worker / beat / mysql(healthy) / redis(healthy)
- 测试：**208 个用例**全过；注释密度 2.3%；ruff / eslint / vite build 均通过
- 分支：`main` 与 `phase2` 都指向 `a8814eb`

## 下一步：S14 退款

口径已定（`plan.md` §13.3）：**仅本人、仅 `PAID`、只做整单退**；退券回 `UNUSED` + 回补库存，
`EFFECTS` 直接复用现成的 `restock` / `return_coupon`。执行顺序：

1. **模型**：`Order.Status` 加 `REFUNDED = 4, "已退款"`；`Order.refunded_at = DateTimeField(null=True, blank=True)`。
2. **规则**：`trade/rules.py` 加 `(PAID → REFUNDED)`，`effects=("restock", "return_coupon")`，
   与 `PENDING → CANCELLED` 用同一套效果函数。
3. **服务**：`trade/services.py` 加 `refund_order(user, order_no, reason="")`——本人否则 404；
   非 `PAID` 抛 `ORDER_STATUS_INVALID`(409)；用现成的 `_apply_transition` 条件更新，
   保证并发下只生效一次；写 `refunded_at`。
4. **接口**：`POST /orders/{order_no}/refund`（登录），返回订单详情。
5. **序列化**：详情加 `refunded_at`；`status_name` 走 `Order.Status(...).name.lower()`，退款后自然是 `refunded`。
6. **对账看板（容易漏）**：`audit/services.py` 的 `RETURNED` 列表要加 `REFUNDED`，
   否则退款回补的库存算不进"回补"，线上立刻变不平；`_order_counts()` 的 labels 也要加 `refunded`。
7. **前端**：`OrdersView` 的 TABS 加「已退款」、`STATUS_TYPES` 加 `4`；
   `PAID` 状态的抽屉里给「申请退款」+ 二次确认；进度时间线加「已退款」节点。
8. **测试**：退款只生效一次（第二次 409 或幂等）、库存与券守恒、非 `PAID` 409、他人 404、
   **退款后 `/audit` 仍平**。
9. **收尾**：写 `docs/phases/phase14.md` → 更新本文件 → 合回 main 上线 → 线上跑一遍退款 →
   最后按 `plan.md` §13.6 **统一重写 README**（结构性大改留到这一步，之前只同步事实性条目）。

## 卡点

无。

## 已定的二期决策（摘要；全文在 `plan.md` §13.3）

| 主题 | 决定 |
|---|---|
| 身份 | 游客 / 普通用户 / 管理员（`is_staff`）；不做多租户、不建角色表 |
| 看板 | `/audit` 免登录只读，只显示 SKU 维度聚合，不含用户信息 |
| 商品 | 30 个（6 类 × 5）；图是 SVG 静态资源，`cover` 只存路径；不造假销量，用 `is_featured` |
| 主题 | **暖色**（米白 + 陶土橙），三版选型已定 |
| 注册 | 用户名 + 密码 + 确认；成功即登录并送「新客满 49 减 5」 |
| 地址 | 收件人 + 手机 + 省市区文本 + 详细地址；不级联；下单时快照（`address_id` 后端必填） |
| 评论 | 仅已支付订单的**明细**可评，每条明细一次，1–5 分，一批整批原子 |
| 退款 | 仅本人、仅 `PAID`、整单退；退券 + 回补，复用 `restock` / `return_coupon` |
| 限流 | 注册 10/h/IP；登录 30/min/IP + 5/min/用户名；Django + Redis，有测试；不做全站 |
| 后台 | Django admin：商品可编辑，订单/券只读；whitenoise + nginx `/static/` 转发 |
| 后台访问 | 公网 `/admin/` 仍 404（C1）；用 SSH 隧道，命令在 `..\ops\demo-account.md` |
| 账号 | `create_demo_user` 加 `--staff`；账号与口令只记 `..\ops\demo-account.md`，不进仓库 |

## 未验证 / 已知边界

- **S9–S13 已在公网生效**：带图商品、注册、购物车（勾选）、地址快照、评论评分、限流、
  `/audit` 看板、一键脚本
- **S14 还没开始**；线上没有退款接口，订单状态仍是 0–3
- README 的**结构性重写**留到 S14 之后（用户明确说现在不着急，只同步事实性条目）
- 一期审查结论只覆盖提交 `4ec7f93`，二期新增代码不在其覆盖范围内
- 首页「热销」是后台手选的 8 个，不是销量排序
- 回滚在"compose 真有差异"时仍没实测（相邻两版 compose 内容相同）
- `PAY_CALLBACK_SECRET` 在服务器 `.env` 里为空，回调签名复用 `SECRET_KEY`
- 限流在 Redis 故障时**放行**（只记 warning），这是主动选择，见 `plan-changes.md` D-014
- 无 HTTPS / 无域名；`ENABLE_MOCK_PAY=true`，任何登录用户能把自己的订单标成已支付

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → `docs/plan.md` §13；要看一期怎么做的，再翻 `docs/phases/`
2. **不要改** `phase0`–`phase8`、`..\check\`、`archive\`
3. 动服务器前读 `..\ops\runbook.md`；每次操作追加 `..\ops\server-log.md`
4. 部署：合回 main 自动部署；只看不动用 Actions → Run workflow → mode `check`
5. 回滚：`ssh aliyun` → `cd /opt/commerce-core && ./deploy.sh <旧 sha>`
6. 推 GitHub 偶发 reset，用一次性参数 `-c http.proxy=http://127.0.0.1:10808`；Gitee 直连
7. **本机一条命令起站**：`powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1`
   （起 Docker、迁移、seed、前后端 :8000 与 :5173，Ctrl+C 一起停）
8. 单跑：`cd backend && .venv\Scripts\python -m pytest -q`（需要 Docker 里的 MySQL/Redis）
9. 新增一个 app 的套路（二期加过 cart / address / review / audit）：
   建目录 + `apps.py` + `__init__.py` + `migrations/__init__.py` → 加进 `INSTALLED_APPS` 与 `config/urls.py`
   → `makemigrations` → 写 `tests/`。**改完 `INSTALLED_APPS` 或 URL 根表必须重启 dev server**
   （`--noreload` 不会加载新 app）。
10. **`.ps1` 存成 UTF-8 带 BOM**：PowerShell 5.1 无 BOM 会按 ANSI 读，中文变乱码还会报语法错；
    Python / JS / Markdown / JSON 则不要 BOM。
11. 踩过的坑：只重建 api 不重建 web 会 502；`docker compose run` 无 TTY 要 `-T`；
    Actions 里步骤 skipped 不会让 job 变红；PowerShell 5.1 吃引号；
    一期那 6 个商品曾缺 `description`，已在 `seed_demo` 的补缺清单里
12. **协作偏好**：动手前先给结论和代价，遇到范围级或拿不准的决策先问；
    汇报要短、不要自我夸奖式的标题；本机临时文件放 `..\.scratch\`（不进仓库）。
