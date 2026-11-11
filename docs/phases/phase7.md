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
- `.github/workflows/ci.yml`：加 `images` job（api + web，sha tag；main 上推 ACR，PR 上只构建不推）
- 本地全栈预演：用 prod compose 在本机（Docker Desktop，Linux 容器）跑 api/web/mysql/redis/worker/beat，
  走一遍登录→领券→下单→支付→关单；WSL2 的 Ubuntu 里再验一次 nginx 静态与 history fallback
- `deploy/.env.prod.example` 补键；`ops/runbook.md` 补部署与回滚固定操作

> `deploy` job 放到 S7b：它需要三个 Secret 和一个已追加公钥的服务器，没有这些就只能写一段没人跑过的 YAML。
> S7a 结束时 CI 只做到"构建 + 推镜像"。

### S7b 部署与回滚（先贴命令、等用户确认再执行）

- 建部署密钥（专用，不用日常私钥）→ 公钥进服务器 → 三个 GitHub Secrets
- `deploy/deploy.sh`（服务器侧：备份 tag → 拉镜像 → 迁移 → 起栈 → 健康检查 → 失败回滚）与 CI 的 `deploy` job
- 首次自动部署：push 到 main → 等 CI 全绿 → 服务器上拉镜像、迁移、起栈、健康检查
- 公网验收：登录 → 领券 → 下单；一单走取消、一单等超时关单；第三单走支付 + PAID 后取消被拒
- 回滚演练：把 IMAGE_TAG 切回上一版 → 重建 → 站点恢复 → 再切回新版本
- 实测记录：`free -m`、`docker stats --no-stream`、各服务内存，写进证据

#### S7b 开工前定下的五件事（2026-11-11 收工，S7a 结束时）

1. **密钥落在仓库外**：`E:\projects\commerce-core\ops\deploy_key`（`ssh-keygen -t ed25519`，不带口令）。
   公钥可以贴给你，私钥不聊天、不进 Git、不进文档，由你自己粘进 GitHub Secrets。
2. **服务器现状是 S2 栈**（4 容器、nginx 用 `nginx:stable` 挂 `.env` 与 conf）。新 compose 是 6 容器，
   `commerce-nginx` 会被 `commerce-web` 替掉，旧的 `/opt/commerce-core/nginx/default.conf` 不再挂载。
3. **回滚演练必须等第二次部署**：ACR 里没有 `web:s2`，第一次从 s2 升到 sha 之后
   `.previous_tag=s2` 是回不去的。所以流程是：部署 sha1 → 再推一个提交部署 sha2 → 从 sha2 回滚到 sha1。
   `deploy.sh` 回滚前先确认目标 tag 的 `api` 与 `web` 两个镜像都存在，缺一个就报错退出、不动现有栈。
4. **compose 文件由 CI 复制到 `/opt/commerce-core/`**，`.env` 一律不动（AGENTS §1.11，用户维护）；
   迁移用 `docker compose run --rm -T api ...`（无 TTY 必须 `-T`，见上面第 3 条坑）。
5. **首次部署后要用户补两个 `.env` 键**：`ENABLE_MOCK_PAY=true`（否则支付按钮 403）、
   `PAY_CALLBACK_SECRET`（独立于 `SECRET_KEY`）。`IMAGE_TAG` 由脚本改写，不用手工填。

## 明确不做

- 不做蓝绿/多机、不宣称零停机（单机 Compose 重建会有秒级不可用）
- 不引入 HTTPS/域名/备案（无域名，用 `http://120.24.67.82:8080`）
- 不在服务器构建任何镜像（含前端）；CI 是唯一构建点
- 不做监控告警全家桶；只保留 health 检查与容器日志
- 不自动拉起 grounded-qa（D-004 已定：失败就回滚，不切栈）

## 门槛

**S7a**

- [x] `docker compose -f deploy/docker-compose.prod.yml up -d` 在本机能起全栈，`/api/v1/health` 200
- [x] 公网同款的 nginx 配置：`/` 返回前端页面、`/assets/*` 命中静态文件、`/orders` 刷新不 404、`/admin/` 404
- [x] worker/beat 真的在跑：造一张已过期订单，60 秒内被关单（实测 3 秒）
- [x] CI 的 build 产出 api 与 web 两个镜像，tag 为 sha；lint/test 仍全绿（run 43019507452，`fee2b17`）
- [x] 本机全栈走通：登录 → 领券 → 下单 → 支付 → 取消/关单

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

### S7a（2026-11-11，本机 Docker Desktop，全是 Linux 容器）

**1. prod compose 起全栈**（`deploy/docker-compose.prod.yml`，与服务器同一份）

```
commerce-api     …/commerce-core/api:local      Up (healthy)
commerce-beat    …/commerce-core/api:local      Up
commerce-mysql   …/commerce-core/mysql:8.0.43   Up (healthy)
commerce-redis   …/commerce-core/redis:7.4.2    Up (healthy)
commerce-web     …/commerce-core/web:local      Up
commerce-worker  …/commerce-core/api:local      Up
```

镜像体积（本地构建）：api **360 MB**、web **240 MB**。`docker compose config -q` 通过。

**2. nginx（配置打进 web 镜像，服务器与本地同一份）**

| 请求 | 结果 |
|---|---|
| `GET /` | 200，`Cache-Control: no-store`，返回 index.html |
| `GET /orders` 直接刷新 | 200，浏览器里被前端守卫转到 `/login?redirect=/orders`，**不是 404** |
| `GET /assets/index-*.js` | 200，`Cache-Control: public, max-age=2592000, immutable`，`Content-Encoding: gzip` |
| `GET /assets/nope.js` | 404（不落到 index.html） |
| `GET /admin/`（来自 172.x） | 302，走内网放行分支 |
| `GET /admin/`（来自 10.99.0.1） | **404**，nginx 日志 `access forbidden by rule, client: 10.99.0.1` |
| `GET /api/v1/health` | 200 `{"status": "ok", "db": true, "redis": true}` |

C1 的 404 分支不是靠读配置确认的：另起一个容器挂在 `10.99.0.0/16`（不在 allow 列表内），用同一份 conf
请求 `/admin/` 得到 404，同一容器上 `/` 与 `/api/v1/health` 仍 200 —— 拦截只落在 `/admin/`。
本机从 127.0.0.1 访问时来源是 172.x，命中放行分支，这也是它显示 302 而不是 404 的原因。

**3. 业务闭环 13/13**（在 api 容器里用 urllib 打 `http://web/api/v1`，走 nginx 反代，不是直连 uWSGI）

| 检查 | 结果 |
|---|---|
| 登录 | 200，拿到 access |
| 商品列表 / 详情含 SKU | 200 / 200 |
| 领券 / 我的券 | 201 / 200（unused=3） |
| 下单（带券） | 201，`discount_amount=30.00` |
| 同 client_token 重放 | 200，返回同一 `order_no`（C5 的幂等路径） |
| 模拟支付 | 200，`status=1`（PAID） |
| 重复支付 | 200（幂等） |
| 已支付再取消 | 409 `ORDER_STATUS_INVALID` |
| 取消订单 | 200，`status=2`（CANCELLED） |
| 已取消再支付 | 409 `ORDER_NOT_PAYABLE` |
| 超时关单 | 订单改到过期后 **3 秒**变 `status=3`（CLOSED） |

**4. worker / beat 真的在跑**

- worker：`celery@… ready.`，任务表里有 `trade.tasks.close_expired_orders`
- beat：`beat: Starting...`，`db -> /tmp/celerybeat-schedule`（写在 tmp，不污染 /app）
- 关单证据就是上表最后一行：库里的 PENDING 订单过期后被改成 CLOSED，不是接口自己算的

**5. 预演挡住的三个问题**

1. **镜像缺 `packaging`**：kombu 的 redis transport `from packaging.version import Version`，而 `packaging` 原先只写在
   `requirements-dev.txt` 里。worker 与 beat 起容器就 `ModuleNotFoundError` 重启，而 `/api/v1/health` 仍然是绿的
   —— api 不碰 broker，健康检查看不出来。修：`packaging` 挪进 `requirements.txt`。
2. **只重建 api 不重建 web = 整站 502**：nginx 启动时解析一次上游地址并缓存，api 容器换 IP 后还打旧地址。
   正常部署两个镜像一起换 tag、一起重建，所以不受影响；手工 `up -d --no-deps api` 之后必须补 `restart web`。
   已写进 `ops/runbook.md`。
3. **`docker compose run` 没有 TTY 时命令跑完仍判失败**：CI 与脚本里必须加 `-T`，否则部署脚本会在
   迁移成功后报错退出。已写进 runbook 与下面的命令清单。
4. **ACR 拒收 buildx 的 attestation 清单**：第一次 CI 在推镜像这一步挂了，报
   `denied: unknown manifest class for application/vnd.oci.empty.v1+json`。buildx 默认给镜像附带
   provenance/SBOM 证明清单（OCI 1.1），阿里云个人版 ACR 不认。修：两个构建步骤都加 `provenance: false`
   与 `sbom: false`，推上去的就是普通单平台镜像。这个报错只在 CI 日志里，本地 `docker build` 看不出来。

**6. CI**

`fee2b17` 的 run **43019507452** 全绿：`lint` 16 s、`test` 48 s、`build & push` 2 分 43 秒，
产出 `api:fee2b17` 与 `web:fee2b17` 两个镜像并推到 ACR（步骤里 `push: true`，推失败会红）。
第一次失败是上面第 4 条，修完复跑即绿。

### S7a 没做 / 明确留到 S7b

- `deploy` job、部署密钥、三个 Secret、服务器上的任何操作
- WSL2 里再跑一遍 nginx：nginx 已经在 Linux 容器里验证，且容器用的就是服务器那个镜像，
  再用 WSL2 跑同一份 conf 提供不了新信息，这一步取消
- `/static/`（Django admin 的 CSS）：admin 只对内网放行，页面能开但没有样式；业务验收不依赖 admin
  （数据由 `seed_demo` 造）。要用 admin 调数据时再单独解决

（S7b 证据待回填）
