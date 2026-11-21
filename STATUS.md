# STATUS

> 更新于 2026-11-21（S15 走查修复已上线）。滚动覆盖，不追加历史。目标：10 秒读完。

## 现在在哪

**一期 S0–S8 已交付并封口**：业务闭环在公网跑通，CI/CD 与回滚演练过，
外部独立审查 10 项全部修完并终审通过（审查对象 `4ec7f93`）。

**二期 S9–S14 已全部上线**：视觉、购物车（含逐行勾选）、地址与快照、评论、限流 / 后台 / 看板 /
一键脚本、**整单退款**。

**S15 走查修复已上线**：注册密码规则提示、导航去重 + 「首页」、订单抽屉按钮对齐、
订单明细带商品名、后台账号可进且隧道登录不再 403（nginx 保留 Host 端口）。

- 公网：`http://120.24.67.82:8080`（无域名无 HTTPS）
- 线上版本：`455f07d`
- 线上数据：30 个商品（6 类 × 5，都有图有详情）、35 个 SKU、3 张券、
  21 张订单（含 `ODDEMO0001`–`ODDEMO0005` 五个演示单，其余是走查时下的）、3 条评价
- **对账看板线上全平**：35 个 SKU，`unbalanced=0`
- 服务器 6 个容器：api(healthy) / web / worker / beat / mysql(healthy) / redis(healthy)
- 后台：`admin` 账号已建（superuser），走 SSH 隧道可进，公网 `/admin/` 仍 404；口令只在 `..\ops\demo-account.md`
- 测试：**232 个用例**全过；注释密度 2.4%；ruff / eslint / vite build 均通过
- 分支：`main` 与 `phase2` 同指（当前 HEAD）
- README 已按 S15 走查结论重写并重拍截图（9 张，全部取自线上）

## 下一步

没有进行中的阶段。想继续的话，候选（**不是承诺**）在 `docs/candidates.md`：
HTTPS 与域名、部分退款、评论带图、商品搜索、看板历史趋势。

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
| 退款 | 仅本人、仅 `PAID`、整单退；退券 + 回补，复用 `restock` / `return_coupon`；重复退 409 |
| 限流 | 注册 10/h/IP；登录 30/min/IP + 5/min/用户名；Django + Redis，有测试；不做全站 |
| 后台 | Django admin：商品可编辑，订单/券只读；whitenoise + nginx `/static/` 转发 |
| 后台访问 | 公网 `/admin/` 仍 404（C1）；用 SSH 隧道，命令在 `..\ops\demo-account.md` |
| 账号 | `create_demo_user` 加 `--staff`；账号与口令只记 `..\ops\demo-account.md`，不进仓库 |
| 演示订单 | `seed_demo_orders`：五个固定单号 `ODDEMO0001`–`ODDEMO0005`，全走真实 service，跑完自检对账 |

## 未验证 / 已知边界

- 二期与 S15 的改动都已在公网验证过：带图商品、注册、购物车（勾选）、地址快照、评论评分、限流、
  `/audit`、一键脚本、退款（页面点过一遍，退款后看板仍平）、后台（隧道登录、商品可编辑、订单只读）
- 退款是 **mock 整单退**：不产生真实资金流，也没有审核环节；部分退款不做
- 退款后已写的评价保留（评价记录的是"买过并用过"）
- 订单明细的商品名只在新单生效：历史订单是快照，仍是旧的"规格名"格式
- README 的截图还是改导航之前的，**整改 README 时要重拍首页、商品列表、订单、后台**
- 一期审查结论只覆盖提交 `4ec7f93`，二期与 S15 的新增代码不在其覆盖范围内
- 首页「热销」是后台手选的 8 个，不是销量排序
- 回滚在"compose 真有差异"时仍没实测（相邻两版 compose 内容相同）
- `PAY_CALLBACK_SECRET` 在服务器 `.env` 里为空，回调签名复用 `SECRET_KEY`
- 限流在 Redis 故障时**放行**（只记 warning），这是主动选择，见 `plan-changes.md` D-014
- 无 HTTPS / 无域名；`ENABLE_MOCK_PAY=true`，任何登录用户能把自己的订单标成已支付、也能整单退款
- 移动端没做响应式（plan §13.2 明确不做），手机上排版会挤
- CI 首次部署时「登录 ACR」出现过一次瞬时失败（重试即成功），原因未查明

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → `docs/plan.md` §13；要看一期怎么做的，再翻 `docs/phases/`
2. **不要改** `phase0`–`phase8`、`..\check\`、`archive\`
3. 动服务器前读 `..\ops\runbook.md`；每次操作追加 `..\ops\server-log.md`
4. 部署：合回 main 自动部署；只看不动用 Actions → Run workflow → mode `check`
5. 回滚：`ssh aliyun` → `cd /opt/commerce-core && ./deploy.sh <旧 sha>`
6. 推 GitHub 偶发 reset，用一次性参数 `-c http.proxy=http://127.0.0.1:10808`；Gitee 直连
   （本机代理端口没开时 GitHub 推不上去，先确认 10808 在监听）
7. **本机一条命令起站**：`powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1`
   （起 Docker、迁移、seed、前后端 :8000 与 :5173，Ctrl+C 一起停）
8. 单跑：`cd backend && .venv\Scripts\python -m pytest -q`（需要 Docker 里的 MySQL/Redis）
9. 三条 seed 命令的顺序是 **建号 → 商品/券 → 订单/评价**：
   `create_demo_user` → `seed_demo` → `seed_demo_orders`（最后这条要 `demo` 账号先存在）
10. 新增一个 app 的套路（二期加过 cart / address / review / audit）：
    建目录 + `apps.py` + `__init__.py` + `migrations/__init__.py` → 加进 `INSTALLED_APPS` 与 `config/urls.py`
    → `makemigrations` → 写 `tests/`。**改完 `INSTALLED_APPS` 或 URL 根表必须重启 dev server**
    （`--noreload` 不会加载新 app）。
11. **`.ps1` 存成 UTF-8 带 BOM**：PowerShell 5.1 无 BOM 会按 ANSI 读，中文变乱码还会报语法错；
    Python / JS / Markdown / JSON 则不要 BOM。**在 PowerShell 里写含反引号的文本要用单引号 here-string**
    （`@'…'@`），否则 `` `t ``、`` `b `` 会被当成转义字符吃掉。
12. 踩过的坑：只重建 api 不重建 web 会 502；`docker compose run` 无 TTY 要 `-T`；
    给容器传环境变量必须 `-e`（`VAR=x docker compose run` 不会进去，命令会自己生成随机口令）；
    Actions 里步骤 skipped 不会让 job 变红；PowerShell 5.1 吃引号，多行远端命令用单引号 here-string
    去掉 `\r` 再管道给 `ssh bash -s`（否则参数尾部带 CR，argparse 报 unrecognized arguments）；
    一期那 6 个商品曾缺 `description`，已在 `seed_demo` 的补缺清单里；
    改订单状态要顺带看 `audit/services.py` 的口径（漏一个状态线上立刻不平）
13. **协作偏好**：动手前先给结论和代价，遇到范围级或拿不准的决策先问；
    汇报要短、不要自我夸奖式的标题；本机临时文件放 `..\.scratch\`（不进仓库）。
