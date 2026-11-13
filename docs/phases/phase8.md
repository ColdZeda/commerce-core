# phase8 — S8 收尾

> 阶段号与 `docs/plan.md` §11 的 S8 对应。目标是"别人拿到这个仓库能看懂、能跑起来"，
> 不是再加功能。

## 目标

把前七个阶段的施工过程收成一份能读的交付物：README 讲清楚它是什么、怎么跑、凭什么可信；
演示数据与演示账号有可重复的做法；失败与取舍有现场记录，而不是只留一句"已完成"。

## 范围

- README 重写：定位、线上入口、链路与状态机、关键设计取舍、接口表、本地运行、测试与 CI、
  部署与回滚、目录、踩过的坑、边界与非目标、常见的追问
- 演示账号命令 `create_demo_user`：口令来自 `DEMO_PASSWORD` 或随机生成并只打印一次，
  **不进仓库、不进文档**
- 压测与 A/B/C 实验的数字整理成一张可引用表，明确标注环境与口径
- 失败记录：假绿、ACR attestation、nginx 缓存上游、`-T`、连接数、乐观锁"卖不完"
- `AGENTS.md` 的代码地图与命令跟上 S7/S8 的实际状态
- `STATUS.md` 收口

## 明确不做

- 不加新接口、新表、新页面
- 不为了"好看"补没有实测来源的数字（QPS、并发上限、内存占比一律不写）
- 不把 README 拆成十份文档（AGENTS §1.20 / C8）
- 不做 HTTPS、域名、备案

## 门槛

- [ ] 新用户只看 README 能跑起后端 + 前端 + 异步关单
- [ ] README 里每个数字都能在 `docs/phases/` 找到出处，或明确标注是计划值
- [ ] 演示账号不依赖仓库里的任何明文口令
- [ ] 失败记录至少包含本阶段真实发生的两件事（假绿、`packaging` 缺失）
- [ ] `pytest` 全绿、`ruff` 干净、注释密度仍低于 5%

## 实施顺序

1. `create_demo_user` 命令 + 测试
2. README 重写
3. `AGENTS.md` 代码地图/命令更新
4. 证据回填、`STATUS.md`、tag `s8`

## 实现级决定

1. **演示账号不做固定口令**。README 里写 `demo/demo1234` 最省事，但等于把口令提交进 Git，
   也和"密码不进仓库"的红线冲突。改成命令 + 环境变量，口令由部署者决定。
2. **命令幂等**：已存在就跳过，`--reset` 才改密码。否则每次部署都会把演示口令洗掉。
3. **随机口令只在生成时打印一次**，之后系统里只有哈希，找不回——这是有意为之。

## 证据

### 1. 演示账号命令（`accounts/management/commands/create_demo_user.py`）

四个用例进 CI（`accounts/tests/test_demo_user.py`）：

| 用例 | 断言 |
|---|---|
| 用 `DEMO_PASSWORD` | 账号能校验该口令，且**输出里不含口令** |
| 不给环境变量 | 输出里能正则出随机口令，且用它登录校验通过 |
| 跑第二次（无 `--reset`） | 输出"已存在"，旧口令仍然有效 |
| `--reset` | 新口令生效、旧口令失效 |

### 2. README 重写

结构：定位与三条可证明的性质 → 线上事实 → 链路与状态机 → 设计取舍表 → A/B/C 实测数字 →
14 个接口表 → 本地运行 → 测试与 CI → 部署与回滚 → 目录 → 踩过的坑 → 边界与非目标 → 常见追问。

其中每个数字都能在 `docs/phases/` 找到出处：A/B/C 表格来自 `phase4.md` E4；
内存与容器数来自 `phase7.md`；回滚耗时 26/28 秒来自 `phase7.md`。

### 3. 检查结果（2026-11-13，CI run 43455130527）

- `pytest`：**103 个用例全过**（新增 4 个演示账号用例），共 72 + 31 个点
- `ruff check` / `ruff format --check`：干净（本地跑过，93 个文件已格式化）
- 注释密度：**1.8%**（54 / 2876 行，上限 5%）
- `check_lock.py`：lock 36 / installed 36 一致
- 依赖锁与前端 eslint 未变

### 4. 部署

这次的 push 同样走了自动部署：`current=e74a682`、`previous=d18ff16`，健康检查 200。
`README.md` 的改动不影响运行时，但既然开了自动部署，文档提交也会部署一次——这是已知代价。

### 5. 本地按 README 从零走一遍（2026-11-13 夜，Windows 开发机）

之前记的"没在干净机器复现"已经补上。开发机重启过，Docker Desktop 是现启的，旧容器全处于 Exited。

| 步骤 | 结果 |
|---|---|
| `docker compose ... up -d mysql redis` | **第一次失败**：`ports are not available ... 127.0.0.1:3307` |
| 诊断 | 3307 落在 Hyper-V 保留区间 3307–3406（`netsh interface ipv4 show excludedportrange`），不是被进程占用 |
| 处置 | `.env` 的 `MYSQL_PORT` / `MYSQL_HOST_PORT` 改 3307 → 13307，重新 `up -d` → mysql/redis 均 healthy |
| `run --rm -T api python manage.py migrate` | `No migrations to apply`（库已是最新） |
| `run --rm -T api python manage.py seed_demo` | 幂等生效：新增 0，当前 6 商品 / 9 SKU / 3 券 |
| `up -d api` + `/api/v1/health` | `{"status":"ok","db":true,"redis":true}`，`/api/v1/products` 返回 6 条 |
| `npm install` + `npm run dev` | Vite 8.3.7 起在 5173；页面返回 `<title>commerce-core</title>`，`/api` 代理打通 |
| `celery worker --pool=solo` | `celery@WDNMD ready.`，任务表含 `close_expired_orders` |
| `celery beat` | `beat: Starting...`，独立进程（Windows 上不能用 `-B`） |
| `pytest -q` | **103 个用例全过**（72 + 31 个点） |

两个新发现已回填 README：

1. **3307 可能被 Windows 保留**，症状像"端口被占"但实际是系统预留 → README 加了排查命令与处置方式。
2. Vite 8 默认只监听 `::1`，`http://127.0.0.1:5173` 会连不上，必须用 `http://localhost:5173`。
   README 原本写的就是 `localhost`，无需改动，但记在这里备查。

**再往前走一步时又发现两个坑（都已回填 README）**

| 现象 | 原因 | 处置 |
|---|---|---|
| 本地 `GET /api/v1/orders` 返回 **404**，但 `/health` 200 | compose 只在镜像不存在时构建，容器跑的是几天前的 `commerce-core-api:s0` | README 的本地步骤里加 `build api`，并说明这个症状 |
| 前端点「模拟支付」403 | api 容器用 `config.settings.prod`，prod 的 `ENABLE_MOCK_PAY` 默认 false（dev settings 才默认 true） | README 加"本地想点支付要设 `ENABLE_MOCK_PAY=true` 再 `--force-recreate api`" |

**本地完整闭环（浏览器实测）**

登录 `demo` → 商品详情 → 提交订单 → 订单页出现 `OD20261113161417077277`（待支付）
→ 点「支付」→ 确认弹窗（"这是模拟支付…"）→ 确定 → 状态变 **已支付**。
截图：`..\assets\s8-local-orders-paid.png`、`..\assets\s8-local-checkout.png`。

同时验证了本地异步链路：worker 与 beat 同时跑时，每 60 秒收到一次 `close_expired_orders`，
返回 `{'scanned': 0, 'closed': 0, 'skipped': 0}`（本地没有过期单，属预期）。

### 6. 公网演示账号（用户决定）

用户判断这是求职 demo，不需要按真实系统对待，所以采用**公开的固定口令**：`demo` / `demo1234`。

- 已在线上创建并验证：`/auth/login` 200、`/auth/me` 返回 `demo`(id=2)、可领券 3 张、订单 0
- 口令写进 README 属于对 AGENTS §1.10 的**有意例外**，理由：这是公开演示账号，数据全是 `seed_demo`
  的假数据，支付是 mock，不关联任何真实系统；换口令仍是 `create_demo_user --reset`
- 命令本身仍支持不给口令时随机生成，哪天想收紧不用改代码

### 7. 没做 / 留给后续

- 需要外部可点链接的场合再考虑域名 + HTTPS（当前明文 8080）
- `.env.example` 里的默认端口仍是 3307，没有因为本机保留区间而改——那不是代码问题，
  改默认值会让已经部署的环境对不上；排障说明放在 README 更合适
