# plan-changes

> 对 `docs/plan.md` 的修订记录。只追加，不改写历史。
> 每条必须能让读者**只看这一条就还原被替换的段落**：写清改的段落、"之前"原文、"现在"是什么。
> 单条超过 40 行，说明这是结构性改动，改用 `archive/plan-YYYYMMDD-HHmm.md` 存快照。

## D-001 定案前的取舍（迁移时补记，2026-11-10）

本条目记录"考虑过但没采用"的方向。`plan.md` 只写最终做法，不写这些；原始讨论目录清理后，这里是唯一留存。

- 否掉 Redis 预扣做主库存：需要双写 + 对账 + 补偿，为不存在的吞吐问题引入不可控的一致性窗口。只保留独立实验。
- 否掉 `countdown=900` 定时关单：ETA 依赖 worker 内存与 broker 重投语义，行为不可预测且难验证；改用 beat 扫表。
- 否掉 `user_coupon.order_id`：与 `order.user_coupon_id` 双向引用必然不一致，保留订单侧单向。
- 否掉 `stock_log` 表：为讲清"扣了没落库"加表会突破六表边界，用结构化日志 + 只读对账脚本替代。
- 否掉乐观锁作为主流程：纯扣减时条件 UPDATE 本身就是 CAS，`version` 不增加正确性，只增加重试成本。
- 否掉 Redis 读缓存：数据量小，一致性成本高于收益。
- 否掉接口限流：无真实用户；且要处理反向代理真实 IP、Redis 故障时放行还是拒绝，收益低于成本。
- 否掉重置服务器：双栈切换可逆且更快，重置的每一步都是新故障点。
- 否掉在 ECS 上构建镜像：1.6GiB 会 OOM，镜像只在 CI 构建。
- 否掉 C 与 A/B 直接比 p99：操作边界不同，只比同一边界下的扣减耗时。

## D-002 S0 落地时的实现级决定（2026-11-10）

`plan.md` 没写死这些细节，按 `AGENTS.md` §1.3 记录取舍；后续改动同样在此追加。

- **settings 分层**：`backend/config/settings/{base,dev,test,prod}.py`。`manage.py` 默认 dev，`wsgi.py` 默认 prod；本地与镜像共用一套代码，只靠 `DJANGO_SETTINGS_MODULE` 区分。
- **`.env` 位置**：仓库根 `.env`（已在 `.gitignore`），`base.py` 用 `load_dotenv` 读取且不覆盖已有环境变量。因此 compose 必须在仓库根带 `--env-file .env`；README/AGENTS 里的旧命令缺这个参数会读不到密码。
- **MySQL 宿主端口 3307**：本机已有 mysqld 占用 3306，容器只绑 `127.0.0.1`。
- **隔离级别显式 `read committed`**（Django 5.2 对 MySQL 的默认值）。理由：一致性与并发控制靠行锁、唯一索引、条件更新，不靠间隙锁；RC 死锁面更小。代价：同一事务内重复读不是快照一致，校验必须紧贴加锁读写。`AGENTS.md` §6 里"RR 下读到快照"只是注释示例，不构成定案。
- **驱动分工**：Windows 用 PyMySQL 垫片（`config/__init__.py` 按平台或 `DB_DRIVER` 选择），Linux 镜像用 mysqlclient。镜像装 `requirements-prod.txt`（mysqlclient + uWSGI），Windows 不装这两个编译型包。
- **版本钉死**：`mysql:8.0.43`、`redis:7.4.2`、`python:3.12-slim-bookworm`、`uwsgi==2.0.31`、`mysqlclient==2.3.0`，不用浮动 tag。
- **compose 项目名 `commerce`**：容器 `commerce-*` 独占一组，与本机其它 compose 项目互不干扰。
- **健康检查路径 `/api/v1/health`**：依据 plan §4.1 的 `/api/v1` 基线与 §4.2 表格里的 `/health`。
- **CI 只用两个 job**：`lint`（ruff、注释检查、eslint）与 `test`（pytest + MySQL/Redis service）。测试库 `test_commerce` 在 CI 用 root 建，本地容器由 `deploy/mysql/init/01-grants.sql` 给应用账号授权。
- **前端路由**：S0 只放 `/` 自检页，四个业务路由等 S1/S2 按 plan §8 落地。

## D-003 S1 的实现级取舍（2026-11-10）

- **错误体**：`config/exceptions.py` 一处收口，`{code,message,detail?}`，status→code 走固定映射表；
  字段级校验错误保留原始 `detail` 结构，前端按字段渲染。业务码（如 `STOCK_NOT_ENOUGH`）到 S3 再按需加。
- **分页**：`config/pagination.py` 统一 10 / 上限 50，参数名 `page`、`page_size`，与 plan §4.1 一致。
- **排序白名单**：只放 `created_at`、`price` 两个字段及各自方向；`price` 排的是**最低在售价**，
  白名单外直接 400，不做静默回退。
- **可见性**：列表与详情都只暴露 `is_active=True` 的商品，详情只带在售 SKU；下架商品访问详情返回 404。
  这样前端不需要判断"下架但可见"的中间态。
- **`order` 表名**：MySQL 保留字，但 plan §3.2 已定案，照用；Django 会给标识符加反引号，
  ORM 与迁移都不受影响，**手写 SQL / 外部工具必须自己转义**。
- **`seed_demo` 幂等**：`get_or_create` 只补缺，不覆盖已存在的价格与库存，避免重跑把演示改价重置。
- **测试位置**：按 app 就近放（`catalog/tests/`），`pytest` 的 `testpaths` 改为收集整个 `backend/`，
  避免新增 app 时忘记加路径。
- **共享基类**：`common/models.TimeStampedModel` 只放 `created_at/updated_at`，不引入更多抽象。

## D-004 S2 前调整的两处（2026-11-10）

- **不再"切回 grounded-qa"**。plan §10.2 与 §11 的 S2 门槛写的是"停 commerce → 切回 grounded 并验证恢复"。
  用户 2026-11-10 明确 grounded-qa 已停用，只需要它让出 8080：**停一次，不再启回**，数据卷保留。
  影响：S2 门槛的"切回并验证"改为"停 grounded → 起 commerce → 外网可达 → 记内存"；
  C4 的失败分支相应变成"commerce 起不来就先停下，别把 8080 空着"，不再自动拉 grounded。
- **顶层工作区文档归位**：`E:\projects\readme.md` 补上服务器共用说明与切换命令；服务器事实与操作流水
  分别落到 `ops/runbook.md`（稳定事实）与 `ops/server-log.md`（只追加的流水）。两者不在 Git 仓库内。



