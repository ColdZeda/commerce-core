# STATUS

> 更新于 2026-11-20（二期计划已定，S9 待开工；一期已封口）。滚动覆盖，不追加历史。目标：10 秒读完。

## 现在在哪

**一期 S0–S8 已交付并封口**：业务闭环在公网跑通，CI/CD 与回滚演练过，
外部独立审查 10 项全部修完并终审通过（审查对象 `4ec7f93`）。

**二期 S9–S14 已立项**：把项目从“能跑”做到“像个店”——注册、购物车、地址、评论、退款（mock）、
30 个商品带图、对账看板、一键脚本、限流。范围与已定决策见 `docs/plan.md` §13。

- 公网：`http://120.24.67.82:8080`（无域名无 HTTPS）
- 线上版本：`5fa7903`（`.current_tag`；一期收口后只动过 README）
- 服务器 6 个容器：api(healthy) / web / worker / beat / mysql(healthy) / redis(healthy)
- 测试：**118 个用例**全过（一期）；注释密度 1.9%；CI 全绿
- 分支：二期在 `phase2` 上开发，**每个阶段完成合回 main**（一次合并 = 一次部署）

## 下一步

**S9 视觉与身份**（预计 4.5 天，验收见 `plan.md` §11 与 §13）：

1. 先出 **3 版首页静态稿**（清爽 / 深色质感 / 暖色亲和）给用户选，选定再铺开；
2. 30 个商品、6 个分类、30 张 SVG 图（`frontend/public/img/products/`）；
3. 首页（分类条 + 热销 8 + 新品 8 + 券）、登录页改版、**注册页**（成功即登录 + 送新人券）；
4. 导航 + footer + 商品详情页改版；
5. 写 `docs/phases/phase9.md`，合回 main，线上验证。

**开工前先读 `docs/plan.md` §13.3「已定实现决策」，不要重新讨论。**

## 卡点

无。

## 已定的二期决策（摘要；全文在 plan §13）

| 主题 | 决定 |
|---|---|
| 身份 | 游客 / 普通用户 / 管理员（`is_staff`）；不做多租户、不建角色表 |
| 看板 | `/audit` 免登录只读，只显示 SKU 维度聚合，不含用户信息 |
| 商品 | 30 个（6 类 × 5）；图是 SVG 静态资源，`cover` 只存路径；不造假销量，用 `is_featured` |
| 注册 | 用户名 + 密码 + 确认；成功即登录并送「新客满 49 减 5」 |
| 地址 | 收件人 + 手机 + 省市区文本 + 详细地址；不级联；下单时快照 |
| 评论 | 仅已完成订单的**明细**可评，每条明细一次，1–5 分 |
| 退款 | 仅本人、仅 `PAID`、整单退；退券 + 回补，复用 `restock` / `return_coupon` |
| 限流 | 注册 10/h/IP；登录 30/min/IP + 5/min/用户名；Django + Redis，有测试；不做全站 |
| 后台 | Django admin：商品可编辑，订单/券只读；whitenoise + nginx `/static/` 转发 |
| 后台访问 | 公网 `/admin/` 仍 404（C1）；用 SSH 隧道，命令在 `..\ops\demo-account.md` |
| 账号 | `create_demo_user` 加 `--staff`；账号与口令只记 `..\ops\demo-account.md`，不进仓库 |

## 未验证 / 已知边界

- **二期一行代码都还没写**：S9 之前的“已完成”只指一期
- 一期审查结论只覆盖提交 `4ec7f93`，二期新增代码不在其覆盖范围内
- 回滚在“compose 真有差异”时仍没实测（相邻两版 compose 内容相同）
- `mode=check` 的只读行为只有本地片段模拟与一次真机 deploy 的旁证
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
8. 踩过的坑：只重建 api 不重建 web 会 502；`docker compose run` 无 TTY 要 `-T`；
   Actions 里步骤 skipped 不会让 job 变红；PowerShell 5.1 吃引号
