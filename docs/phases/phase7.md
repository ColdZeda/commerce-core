# phase7 — S7 部署与 CI/CD

> 阶段号与 `docs/plan.md` §11 的 S7 对应。分两段做：**S7a 本地与 CI（服务器不动）**、**S7b 部署与回滚（要用户确认）**。
> 阶段结束封口，不再追加；新内容进 phase8。

## 目标

把已经跑通的本机闭环搬到公网：push 一次 → CI 构建推镜像 → 服务器拉新镜像 → 迁移 → 起栈 → 健康检查；
并且证明**改坏了能退回来**。同时补齐两件现在缺的东西：nginx 托管前端静态资源、compose 里的 worker/beat。

## 范围

### S7a 本地与 CI（不碰服务器）

- `deploy/Dockerfile.web`：node 24 构建前端 → nginx:stable 运行，内置 conf 与 dist（独立"静态产物镜像"）
- `deploy/nginx/default.conf` 改造：`/api/` 反代、`/admin/` 仍按 C1 返回 404、`/assets/` 长缓存、
  `index.html` no-store、history fallback 到 `index.html`
- `deploy/docker-compose.prod.yml`：nginx 服务换成 web 镜像；新增 `worker`、`beat` 两个 service（同一 api 镜像）
- `.github/workflows/ci.yml`：加 `build`（api + web，sha tag）与 `push`（ACR）；
  `deploy` job 在 main 上跑（SSH → 迁移 → up → health → 失败回滚）
- 本地全栈预演：用 prod compose 在本机（Docker Desktop，Linux 容器）跑 api/web/mysql/redis/worker/beat，
  走一遍登录→领券→下单→支付→关单；WSL2 的 Ubuntu 里再验一次 nginx 静态与 history fallback
- `deploy/.env.prod.example` 补键；`ops/runbook.md` 补部署与回滚固定操作

### S7b 部署与回滚（先贴命令、等用户确认再执行）

- 建部署密钥（专用，不用日常私钥）→ 公钥进服务器 → 三个 GitHub Secrets
- 首次自动部署：push 到 main → 等 CI 全绿 → 服务器上拉镜像、迁移、起栈、健康检查
- 公网验收：登录 → 领券 → 下单；一单走取消、一单等超时关单；第三单走支付 + PAID 后取消被拒
- 回滚演练：把 IMAGE_TAG 切回上一版 → 重建 → 站点恢复 → 再切回新版本
- 实测记录：`free -m`、`docker stats --no-stream`、各服务内存，写进证据

## 明确不做

- 不做蓝绿/多机、不宣称零停机（单机 Compose 重建会有秒级不可用）
- 不引入 HTTPS/域名/备案（无域名，用 `http://120.24.67.82:8080`）
- 不在服务器构建任何镜像（含前端）；CI 是唯一构建点
- 不做监控告警全家桶；只保留 health 检查与容器日志
- 不自动拉起 grounded-qa（D-004 已定：失败就回滚，不切栈）

## 门槛

**S7a**

- [ ] `docker compose -f deploy/docker-compose.prod.yml up -d` 在本机能起全栈，`/api/v1/health` 200
- [ ] 公网同款的 nginx 配置：`/` 返回前端页面、`/assets/*` 命中静态文件、`/orders` 刷新不 404、`/admin/` 404
- [ ] worker/beat 真的在跑：造一张已过期订单，60 秒内被关单
- [ ] CI 的 build 产出 api 与 web 两个镜像，tag 为 sha；lint/test 仍全绿
- [ ] 本机全栈走通：登录 → 领券 → 下单 → 支付 → 取消/关单

**S7b**

- [ ] push 一次自动部署成功（服务器不构建，只 pull）
- [ ] 公网完成三单验收：取消、超时关单、支付 + PAID 后取消 409
- [ ] 手动回滚成功：切回上一 tag → 站点恢复 → 再切回新版
- [ ] 迁移先于 `up -d` 执行，且失败时栈保持可用（或回滚到旧 tag）
- [ ] 内存实测写在证据里；超过 2 GiB 按 §10.3 的顺序降级并记录代价
- [ ] 全过程写进 `ops/server-log.md`；固定操作写进 `ops/runbook.md`

## 实施顺序

1. `Dockerfile.web` + nginx conf + compose（web/worker/beat）
2. 本机 prod compose 全栈预演（含 worker 关单）
3. CI：build + push（ACR），先不接 deploy
4. 部署密钥与三个 Secrets → deploy job
5. S7b：首次部署 → 三单验收 → 回滚演练 → 记录
6. 证据回填、`STATUS.md`、推送

## 实现级决定（先记理由再实施，AGENTS §1.3）

1. **静态资源打成独立 web 镜像**（node build → nginx），替掉现在直接用的 `nginx:stable`。
   plan §10.4 要求"前端/静态产物镜像"，服务器又不许构建；一个容器同时管静态和 `/api/` 反代，
   端口仍是 8080，不新增容器数。镜像体积换部署简单，接受。
2. **worker 与 beat 用同一个 api 镜像、不同 command**，不单独构建。
   beat 必须独立进程（Windows 上 `-B` 会被 Celery 拒绝，Linux 上也更容易观察）；
   若内存超限，按 plan §10.3 顺序：先把 beat 合进 worker（`-B`），再降 uWSGI 到 1 process / 4 threads。
3. **`IMAGE_TAG` = git sha 前 7 位**。服务器 `/opt/commerce-core/.current_tag` 与 `.previous_tag`
   由部署脚本维护；回滚就是"把 `.previous_tag` 写回 `.env` 的 `IMAGE_TAG` 再 `up -d`"，
   不需要重新构建，也不需要改 compose。
4. **迁移在 `up -d` 之前跑**：`docker compose run --rm api python manage.py migrate`。
   旧代码必须能在新库上跑（plan §3.4 的加法迁移纪律），所以顺序是 迁移 → 起新栈。
5. **SSH 用专用部署密钥**，公钥追加到服务器 `~/.ssh/authorized_keys`，私钥只进 GitHub Secrets
   （`DEPLOY_HOST` / `DEPLOY_USER` / `DEPLOY_SSH_KEY`）。不用第三方 action，直接 `ssh`，
   免得把权限面交给一个不认识的市场 Action。
6. **失败分支按 D-004 改写**：plan C4 原文是"停 commerce → 起 grounded → 验证 → 报错退出"，
   但 grounded-qa 已停用（D-004）。现在的失败分支是：**先回滚到 `previous_tag`，确认站点恢复，
   再把失败原因报出来**；不自动切到另一个项目。
7. **缓存策略**：`/assets/` 带 hash，`expires 30d, immutable`；`index.html` 与 SPA 路由 `no-store`，
   否则改了前端用户还拿旧的 index。`/admin/` 保持 C1 的 404。
8. **服务器 `.env` 增三个键**：`ENABLE_MOCK_PAY=true`（公网演示要能点支付）、
   `PAY_CALLBACK_SECRET`（独立于 SECRET_KEY）、`IMAGE_TAG`（部署脚本改写）。
   `.env` 仍由用户维护，CI 只读不写。

## S7b 命令清单（草案，执行前再贴一次并等确认）

```bash
# 0. 本地：推到 main，等 CI 的 build/push 绿，记下 sha
git rev-parse --short HEAD

# 1. 服务器：登录 ACR（密码轮换过，必须重新登录）
ssh aliyun
cd /opt/commerce-core
docker login crpi-3tubdvd6wrolewii.cn-shenzhen.personal.cr.aliyuncs.com

# 2. 备份当前 tag，写入新 tag
cp .current_tag .previous_tag
echo <新sha> > .current_tag
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=<新sha>/" .env

# 3. 拉镜像 → 迁移 → 起栈
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml run --rm api python manage.py migrate
docker compose -f docker-compose.prod.yml up -d

# 4. 验证
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:8080/api/v1/health
curl -fsS http://127.0.0.1:8080/api/v1/products | head -c 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/
free -m && docker stats --no-stream
```

回滚：

```bash
cd /opt/commerce-core
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$(cat .previous_tag)/" .env
docker compose -f docker-compose.prod.yml up -d
curl -fsS http://127.0.0.1:8080/api/v1/health
```

## 需要用户做的事

- [x] `ACR_USERNAME` / `ACR_PASSWORD`（commerce-core 仓库，2026-11-11 已加）
- [ ] 部署密钥：我在 S7b 前生成一对专用密钥，把公钥贴给你，你追加到服务器 `~/.ssh/authorized_keys`；
      私钥由你填进 GitHub Secrets 的 `DEPLOY_SSH_KEY`（不经过聊天）
- [ ] `DEPLOY_HOST`（`120.24.67.82`）、`DEPLOY_USER`（`root` 或你的登录名）两个 Secret
- [ ] S7b 执行前的确认：我会把上面的命令清单原样贴出来，你点头再动服务器

## 已知风险

- **内存**：2 vCPU / 2 GiB 上再叠 worker + beat，可能顶到边界。S7a 先在本机估，
  S7b 用 `free -m` 实测；超了按 §10.3 降级，不硬撑。
- **`ENABLE_MOCK_PAY=true` 是公网可点的 mock 支付**：任何人登录后都能把订单标成已支付。
  这是演示项目的取舍，写进 README 的非目标里，不包装成真实支付。
- **回滚只回镜像不回数据库**：迁移必须加法，否则旧镜像配新库会读错列。

## 证据

（实施后回填）
