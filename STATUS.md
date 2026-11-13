# STATUS

> 更新于 2026-11-13（S7b 首次部署成功）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S7a 已完成；S7b 首次部署成功**，业务闭环已经上公网：
登录 → 领券 → 下单 → 取消 / 超时关单 → 模拟支付。

- 公网地址 `http://120.24.67.82:8080`（无域名无 HTTPS，端口 8080）
- 当前部署 sha：**`da630e9`**（`.current_tag`），上一版记录是 `s2`（无 web 镜像，回滚不可用）
- 服务器 6 个容器：api(healthy) / web / worker / beat / mysql(healthy) / redis(healthy)
- 内存实测 available **734 MB**，容器合计约 465 MiB，**未触发任何降级**
- CI：lint + test + build&push 全绿；`deploy` job 目前只能手动触发（`workflow_dispatch`）

**S7b 已完成的部分**：

- 专用部署密钥 `commerce-core-deploy` 已加到服务器，私钥在仓库外 `..\ops\deploy_key`
- 五个 Secrets 齐全；`.env` 补了 `ENABLE_MOCK_PAY=true`
- `deploy/deploy.sh`：预检 → 改 tag → pull → **迁移** → up → 健康检查 → 失败回滚（本地假 docker 演练 25/25）
- 首次部署 + 公网三单验收 13/13（支付后取消 409、取消后支付 409、超时 9 秒关单）

阶段记录：`docs/phases/phase0.md` … `phase7.md`；服务器事实与流水在仓库外
`..\ops\runbook.md` 与 `..\ops\server-log.md`。

## 下一步

**S7b 收尾还剩三件**（都还需要一次部署，合计约 10 分钟）：

1. **回滚演练**：需要第二个 sha。有了它，`.previous_tag` 指向 `da630e9`（api+web 都在），
   才能真正演练 `sha2 → da630e9 → sha2`；现在 `previous=s2` 是回不去的
2. **自动部署**：把 `deploy` job 的 `if` 改成"push 到 main 也跑"，那一次推送本身就是
   "push 一次自动部署成功" 的证据。**这是一条策略变更：开启后每次 push main 都会部署**
3. 证据回填 `phase7.md`、`STATUS.md`、tag `s7b`

之后的 **S8 收尾**：README、架构/契约/状态机/测试/部署/压测/取舍文档、演示数据与 demo 用户
（公网 demo 怎么安全初始化还没定）、面试讲述。

## 卡点

无。

## 未验证（不许当成已完成）

- 回滚演练没做（缺第二个 sha，见上）
- 自动部署没开（当前只有手动 dispatch 能部署）
- `PAY_CALLBACK_SECRET` 在服务器 `.env` 里为空，回调签名回落到 `SECRET_KEY`；
  公网没有真实支付通道，`/payments/callback` 只有测试覆盖过
- Django admin 的 `/static/` 没托管：内网能开页面但没有样式，业务验收不依赖它
- 公网 demo 用户的安全初始化方式（S8）
- 无 HTTPS / 无域名，公网明文；`ENABLE_MOCK_PAY=true` 意味着任何登录用户都能把订单标成已支付

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → `docs/phases/phase7.md`（S7b 证据已回填）
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. **部署方式**：GitHub Actions → CI → Run workflow → 分支 main → mode 选 `deploy`
   （需要 token；本机 `git credential fill` 里有可用 PAT，`gh` 本身未登录）
4. 推 GitHub 直连即可，偶发 reset 就重试；Gitee 直连
5. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`；前端 `cd frontend && npm run dev`
6. 生产栈本机预演：`cd deploy && docker compose -f docker-compose.prod.yml up -d`（要先停本地栈，容器名会撞）
7. 踩过的坑：只重建 api 不重建 web 会整站 502（nginx 缓存上游 IP）；
   `docker compose run` 在无 TTY 环境必须加 `-T`；PowerShell 5.1 传参吃引号，
   远端脚本周转用"上传 .sh 再执行"而不是内联
