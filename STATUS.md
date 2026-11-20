# STATUS

> 更新于 2026-11-21（S13 已上线并验证）。滚动覆盖，不追加历史。目标：10 秒读完。

## 现在在哪

**一期 S0–S8 已交付并封口**：业务闭环在公网跑通，CI/CD 与回滚演练过，
外部独立审查 10 项全部修完并终审通过（审查对象 `4ec7f93`）。

**二期**：S9 视觉、S10 购物车（含逐行勾选）、S11 地址与搜索、S12 评论、S13 运营与看板都已上线。
只剩 S14 退款。

- 公网：`http://120.24.67.82:8080`（无域名无 HTTPS）
- 线上版本：`612dcdb`（`.current_tag`）
- 线上数据：30 个商品（6 类 × 5）、35 个 SKU、3 张券、1 条地址、1 条评价；**对账看板显示 35 个 SKU 全平**
- 服务器 6 个容器：api(healthy) / web / worker / beat / mysql(healthy) / redis(healthy)
- 测试：**208 个用例**全过；注释密度 2.3%
- 分支：`main` 与 `phase2` 都指向 `612dcdb`

## 下一步

**S14 退款**：`PAID → REFUNDED` 规则、退券与回补库存、退款接口与按钮。
做完合回 main，再按 §13.6 统一重写 README。

## 卡点

无。

## 卡点

无。

## 已定的二期决策（摘要；全文在 plan §13）

| 主题 | 决定 |
|---|---|
| 身份 | 游客 / 普通用户 / 管理员（`is_staff`）；不做多租户、不建角色表 |
| 看板 | `/audit` 免登录只读，只显示 SKU 维度聚合，不含用户信息 |
| 商品 | 30 个（6 类 × 5）；图是 SVG 静态资源，`cover` 只存路径；不造假销量，用 `is_featured` |
| 主题 | **暖色**（米白 + 陶土橙），三版选型已定 |
| 注册 | 用户名 + 密码 + 确认；成功即登录并送「新客满 49 减 5」 |
| 地址 | 收件人 + 手机 + 省市区文本 + 详细地址；不级联；下单时快照 |
| 评论 | 仅已完成订单的**明细**可评，每条明细一次，1–5 分 |
| 退款 | 仅本人、仅 `PAID`、整单退；退券 + 回补，复用 `restock` / `return_coupon` |
| 限流 | 注册 10/h/IP；登录 30/min/IP + 5/min/用户名；Django + Redis，有测试；不做全站 |
| 后台 | Django admin：商品可编辑，订单/券只读；whitenoise + nginx `/static/` 转发 |
| 后台访问 | 公网 `/admin/` 仍 404（C1）；用 SSH 隧道，命令在 `..\ops\demo-account.md` |
| 账号 | `create_demo_user` 加 `--staff`；账号与口令只记 `..\ops\demo-account.md`，不进仓库 |

## 未验证 / 已知边界

- **S9–S13 已上线**：30 个商品带图有详情、注册可用、购物车（含勾选）、地址与下单快照、评论与评分、
  限流（注册 10/h/IP、登录 30/min/IP + 5/min/用户名）、`/audit` 看板、一键脚本都在公网生效
- 一期审查结论只覆盖提交 `4ec7f93`，二期新增代码不在其覆盖范围内
- 注册与登录**还没有限流**（S13 统一接）
- 首页「热销」是后台手选的 8 个，不是销量排序
- 回滚在"compose 真有差异"时仍没实测（相邻两版 compose 内容相同）
- `PAY_CALLBACK_SECRET` 在服务器 `.env` 里为空，回调签名复用 `SECRET_KEY`
- 无 HTTPS / 无域名；`ENABLE_MOCK_PAY=true`，任何登录用户能把自己的订单标成已支付

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → `docs/plan.md` §13；要看一期怎么做的，再翻 `docs/phases/`
2. **不要改** `phase0`–`phase8`、`..\check\`、`archive\`；二期记录从 `phase9.md` 开始
3. 动服务器前读 `..\ops\runbook.md`；每次操作追加 `..\ops\server-log.md`
4. 部署：合回 main 自动部署；只看不动用 Actions → Run workflow → mode `check`
5. 回滚：`ssh aliyun` → `cd /opt/commerce-core && ./deploy.sh <旧 sha>`
6. 推 GitHub 偶发 reset，用一次性参数 `-c http.proxy=http://127.0.0.1:10808`
7. 本机：`cd backend && .venv\Scripts\python -m pytest -q`（需要 Docker 里的 MySQL/Redis）
8. 前端联调：`backend → manage.py runserver 8000` + `frontend → npm run dev`（vite 代理 `/api` 到 8000）
9. 踩过的坑：只重建 api 不重建 web 会 502；`docker compose run` 无 TTY 要 `-T`；
   Actions 里步骤 skipped 不会让 job 变红；PowerShell 5.1 吃引号
