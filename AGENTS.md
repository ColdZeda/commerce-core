# AGENTS.md — commerce-core

> 执行会话的入口。每次新会话开始或上下文压缩后，**先读本文件**，再读 `STATUS.md` 与 `docs/phases/` 下当前阶段文件。
> 本文件放行为约束与红线；施工内容在 `docs/plan.md`；进度在 `STATUS.md`；改动理由在 `docs/plan-changes.md`。

## §1 红线（违反即返工）

### 范围与决策

1. **不重开已定案**。技术方案已定死，见 `docs/plan.md` §0.1。讨论阶段已结束，不要再发方案评选。
2. **范围级改动必须先问用户**：新增表／页面／接口、C 方案接入主流程、加限流或缓存、重置服务器、更换主要技术栈、要求两个项目同时在线。
3. 实现级改动（文件布局、写法、补丁版本、MySQL 参数、端口、测试 fixture）可以自己定，但**先记录原因再实施**。

### 服务器与仓库

4. 服务器上只操作 commerce-core 自己的栈。任何会停服务、切栈、改配置的动作，**先说明再执行**。
5. 永不执行 `docker system prune -a`、`docker volume prune`、`docker compose down -v`。
6. 防火墙／安全组只由用户在控制台修改，不代操作。
7. 不在服务器上构建镜像（1.6GiB 会 OOM）。镜像只在 CI 构建。
8. 不擅自创建远程仓库、不擅自 push。GitHub 仓库由用户创建。
9. 不修改 `E:\projects\django-test`（教学区），不把代码写回那里。

### 密钥与数据

10. 密码、SSH 私钥、ACR 凭据不进聊天、不进 Git、不进文档。
11. 服务器 `/opt/commerce-core/.env` 由用户手工创建，CI 不覆盖。
12. `archive/` 下是只读冻结件，**永不修改、永不删除**（Windows 上已设只读属性，别去取消）。

### 硬性实现约束 C1–C8

13. **C1** `/admin/` 不暴露公网：nginx 只允许 127.0.0.1／内网网段，其余 404。
14. **C2** 服务器最小栈含 redis；`/health` 必须校验 redis，不许改成"可选"。
15. **C3** 超时链：`innodb_lock_wait_timeout=10` < `harakiri=30` < nginx `uwsgi_read_timeout=35`。
16. **C4** 部署失败分支：停 commerce → 起 grounded → 验证页面 → 再报错退出。
17. **C5** `order_no` 规则写明格式＋唯一索引＋冲突重试一次；`client_token` 每次进结算页生成、下单成功后失效；捕获唯一冲突后的回查必须在 `atomic` 块**之外**。
18. **C6** 下单顺序：锁 SKU（同时取价）→ 校验库存 → 算总额 → 校验券门槛 → 核销券 → 扣减 → 写单。
19. **C7** S0 的 CI 只跑 lint + test；build／push／deploy 到 S7 再接。
20. **C8** 文档结构见 §5，不新增同义文件，不拆十份。

### 叙事与数字

21. Django／MySQL／Celery 是**项目级实操**，不包装成生产级高并发。
22. 不写 QPS 口号、不写"零停机"、不虚构压测／内存／线上结果。
23. 未实测的数字标注"计划值"，实测后改"实测值"；两者不允许混写。

### 注释

24. 违反 §6 视为**未完成**，不进验收。

## §2 常用命令（S0 实测后修正，2026-11-10）

```bash
# 依赖与环境（Windows 开发机；Linux 镜像用 requirements-prod.txt）
cd backend && py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt

# 本地栈（仓库根执行；.env 在仓库根，所以要带 --env-file）
docker compose -f deploy/docker-compose.yml --env-file .env up -d
docker compose -f deploy/docker-compose.yml --env-file .env run --rm api python manage.py migrate

# 检查
cd backend && pytest -q
cd backend && ruff check . && ruff format --check .
python scripts/check_comments.py backend
cd frontend && npm run lint
```

> 网络：本机代理在 `127.0.0.1:10808`（浏览器走系统代理，git 默认直连，所以连 GitHub 会间歇失败）。
> 推 GitHub 时用一次性参数，不改全局配置：`git -c http.proxy=http://127.0.0.1:10808 push origin main`。
> Gitee 是国内直连，不要带代理。连不上先让用户确认代理已开，不要反复重试。

## §3 当前阶段

看 `STATUS.md`。阶段记录在 `docs/phases/phaseN.md`，编号与 `docs/plan.md` §11 的阶段号一一对应。

## §4 代码地图（目录级；S1 后更新）

```
repo/
├─ backend/
│  ├─ config/    settings 分层、URL 根表、分页、异常收口
│  ├─ accounts/  登录/刷新/me，Bearer 认证与 token 错误分类
│  ├─ catalog/   商品与 SKU：模型、列表/详情接口、admin、seed_demo、tests
│  ├─ promotion/ 券与用户券：模型、列表/领取/我的券、领券 service、并发测试
│  ├─ trade/     订单与明细的模型（接口在 S3）
│  ├─ health/    就绪探针
│  ├─ common/    抽象模型（时间戳）与业务错误类型
│  ├─ tests/     跨 app 测试
│  └─ scripts/   db_smoke、check_lock
├─ frontend/     Vue 3 + Vite SPA：/login、/products（含领券入口）、api 层与 auth store；
│                商品详情与订单页在 S3
├─ deploy/       docker-compose.yml、Dockerfile、uwsgi.ini、mysql/init
├─ experiments/  C 方案（Redis 预扣）独立实验，不接默认下单链路（S4）
├─ scripts/      CI 检查脚本（check_comments.py）
├─ docs/         计划、修订记录、阶段记录
└─ .github/      CI：lint + test
```

仓库之外（同一工作区 `E:\projects\commerce-core\`，不是 Git 仓库的一部分）：

```
├─ repo/     正式 Git 仓库，即上面这棵树
├─ ops/      runbook.md（这台机器的事实与固定操作）、server-log.md（每次服务器操作流水，仅做追加写入不做修改）、server.env（服务器 .env 的本地模板，填完上传，不进 Git）
├─ archive/  只读冻结件，永不修改、永不删除（§1.12）
└─ assets/   截图等素材
```

动服务器前先读 `ops/runbook.md`；每次连接服务器做过什么（哪怕只读）都往 `ops/server-log.md` 追加一条。

不确定改哪个文件时先读这里；这里只写到目录级，细到文件的清单一定会过期，**过期的地图比没有更糟**。

## §5 文档索引

| 文件 | 作用 | 何时变 |
|---|---|---|
| `docs/plan.md` | 唯一施工基线：做什么、做成什么样、什么顺序、什么门槛 | 阶段边界、设计变更 |
| `docs/plan-changes.md` | 对 plan 的修订记录，每条带"之前／现在"，只看它就能还原某段 | 每次改 plan |
| `docs/candidates.md` | 人类收件箱，AI **不需要读** | 用户自己写 |
| `docs/phases/phaseN.md` | 单阶段执行记录与验证证据，封口后不再改 | 阶段内 |
| `STATUS.md` | 10 秒指针：现在在哪、下一步、卡点、未验证 | 每轮 |

## §6 注释规范（违反即未完成）

原则：注释解释"为什么"，不解释"做什么"。代码能读出来的，一律不写。
过期的注释比没有注释更糟：改逻辑必须同步改注释，拿不准就删。

**禁止**（出现即删，`scripts/check_comments.py` 会查）：

1. 步骤旁白：`# 1. 查询用户`、`# 然后扣库存`、`# 下面开始校验`
2. 签名复述：`# 参数 sku_id：SKU 的 ID`；`"""获取商品列表"""` 挂在 `list_products` 上
3. 历史叙事：`# 之前用的是 select_for_update，后来改成……`（这属于 `plan-changes.md`）
4. 自我免责／空头待办：`# 这里简单处理`、`# TODO 以后优化`、`# 注意生产环境需要加锁`
5. 分区横幅：`# ===== 工具函数 =====`、`# ---------- 业务逻辑 ----------`
6. 面向面试的话：任何"这个可以在面试里讲"的表述
7. 被注释掉的旧代码：要么删，要么靠 git 历史

**允许且鼓励**：

- 反直觉的实现：为什么这里必须条件更新，而不是先查后改
- 业务规则来源：15 分钟来自运营规则，不是随手写的
- 踩过的坑：RR 隔离级别下这里会读到快照，所以必须……
- 复杂表达式上方一行说明（正则、复杂 SQL、位运算）
- 公开 service 的 docstring：只写输入／输出／抛什么异常，不写实现步骤

密度：注释行 / 代码行 < 5%；单函数 ≤ 2 处；模块顶部说明 ≤ 5 行。
语言：注释用中文、标识符用英文，一句话里不混。
豁免：迁移文件、自动生成的代码。
