# STATUS

> 更新于 2026-11-11（S7a 收口）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S6 已完成**，业务闭环在本地跑通：登录 → 领券 → 下单 → 取消 / 超时关单 → 模拟支付。
代码在 `github.com/ColdZeda/commerce-core`（镜像 `gitee.com/ColdZeda/commerce-core`），
tag：`s0`、`s2`、`s3`、`s4`、`s5`、`s6`。

**S7a 已完成（本机与 CI，服务器没动）**：

- `deploy/Dockerfile.web`：node 构建 → nginx 运行，dist 与 conf 都打进镜像；`api:local` 360 MB、`web:local` 240 MB
- `deploy/nginx/default.conf`：`/` 托管 SPA、`/assets/` 30 天 immutable、`index.html` no-store、
  history fallback、`/api/` 反代、`/admin/` 仍按 C1 返回 404（已用 10.99.0.0/16 网段实测 404）
- `deploy/docker-compose.prod.yml`：六个 service（mysql/redis/api/web/worker/beat），conf 不再挂载，
  每个 service 加了 json-file 日志上限（10m×3）
- `.github/workflows/ci.yml` 加 `images` job：lint+test 全绿后构建 api 与 web，main 上推 ACR（sha tag），PR 上只构建
- 本机全栈预演 13/13：登录→领券→下单（券减 30）→支付→幂等重放→取消→409 分支→过期订单 **3 秒**被 worker 关掉
- CI 全绿（run 43019507452，`fee2b17`）：lint 16 s、test 48 s、build & push 2 分 43 秒，
  `api:fee2b17` 与 `web:fee2b17` 已推到 ACR

**服务器**：`http://120.24.67.82:8080`，4 个容器（api/mysql/redis/nginx）healthy；
服务器上跑的仍是 **S2 镜像**，S3–S7a 的代码都没部署。

阶段记录：`docs/phases/phase0.md` … `phase7.md`（S7a 证据已回填）；服务器事实与流水在仓库外
`..\ops\runbook.md` 与 `..\ops\server-log.md`。

## 下一步

**S7b 部署与回滚**（`docs/phases/phase7.md`；全部要先贴命令、等你确认再动服务器）：

1. 生成专用部署密钥 → 你把公钥追加到服务器 `~/.ssh/authorized_keys`
2. 你在 GitHub Secrets 里填 `DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_SSH_KEY`（私钥不进聊天）
3. `deploy/deploy.sh` + CI 的 `deploy` job（ssh → 备份 tag → 拉镜像 → `migrate -T` → `up -d` → health → 失败回滚）
4. 首次部署 → 公网三单验收（取消 / 超时关单 / 支付后取消 409）→ 回滚演练 → `free -m` 与 `docker stats` 实测

## 卡点

GitHub 这会儿连不上（`Recv failure: Connection was reset`，试了 3 次）。**`75ebf8d` 目前只在本地与 Gitee**，
明天开机第一件事：在 `repo/` 里 `git push origin main`（tag `s7a` 已经推上去了，不用重推）。
推上去会顺带触发一次 CI，正常应该还是绿的。

## 未验证（不许当成已完成）

- S3–S7a 代码还没上服务器：公网仍是 S2 镜像，`/api/v1/orders` 仍是 404
- 公网部署、三单验收、回滚演练、服务器内存实测（S7b）
- Django admin 的 `/static/` 没托管：内网能开页面但没有样式；业务验收不依赖 admin
- 公网 demo 用户的安全初始化方式（S8）

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → 当前阶段文件（`docs/phases/phase7.md`，从 S7b 开始；
   S7b 的前置五件事写在那一节的「开工前定下的五件事」里）
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. 推 GitHub 要带本机代理 `-c http.proxy=http://127.0.0.1:10808`；推 Gitee 直连
4. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`；前端 `cd frontend && npm run dev`
   （本地栈的 api 容器占着 8000，跑 `runserver` 前先 `docker stop commerce-api`）
5. 生产栈本机预演：`cd deploy && docker compose -f docker-compose.prod.yml up -d`，
   需要 `deploy/.env`（模板 `deploy/.env.prod.example`），且要先停下本地栈，容器名会撞
6. 踩过的坑：只重建 api 不重建 web 会整站 502（nginx 缓存了上游 IP），补 `restart web`；
   `docker compose run` 在脚本里必须加 `-T`
7. 异步关单本地演练（Windows 上 beat 与 worker 必须分两个进程）：
   `celery -A config worker -l info --pool=solo` 与 `celery -A config beat -l info`
8. 模拟支付：dev 默认开；prod 要在 `.env` 里设 `ENABLE_MOCK_PAY=true` 才能点「支付」
