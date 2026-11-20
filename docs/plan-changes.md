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

## D-005 S2 前端与镜像引导方式（2026-11-10）

- **S2 上服务器的镜像从本机构建**。AGENTS 只禁止"在服务器上构建"（1.6 GiB 会 OOM），而 CI 的 build/push
  按 C7 要到 S7 才接。所以 S2 用：本机 `docker build` → `docker push` 到 ACR `commerce-core/api:<tag>` →
  服务器 `docker compose pull`。每次手工推的 tag 记在 `ops/server-log.md`，S7 起由 CI 取代。
- **access 有效期做成可配**：`JWT_ACCESS_MINUTES`（默认 15）。S2 验证 401 单飞时临时设成 0.05 分钟，
  这不是测试专用开关，生产也允许调。
- **前端目录**：`src/api/{client,auth,catalog,coupons}.js`、`src/stores/auth.js`、`src/views/{LoginView,ProductsView}.vue`。
  axios 与 store 之间用 `configureAuth()` 注入回调，避免循环依赖。
- **路由**：目前只有 `/` → `/products`、`/login`、`/products`，未匹配路径一律回商品页；
  商品详情页与订单页按 plan §8 在 S3 一起做。

## D-006 S4 实验区位置与压测环境（2026-11-11）

- **实验代码放 `backend/stocklab/`，不建仓库根的 `experiments/`**。plan §6.3 写的是"`experiments/` 可由
  pytest 收集并进入 CI"，但本仓库三个质量入口都以 `backend/` 为根：`pytest` 的 `testpaths=["."]`、
  lint job 里的 `ruff check .`、`scripts/check_comments.py backend`。放根目录要同时改三处配置并给 pytest
  补 `sys.path`，才能让实验代码被收集、被 lint、被注释检查；放 `backend/stocklab/` 一处都不用改。
  影响：AGENTS §4 代码地图与 README 的目录说明同步改成 `backend/stocklab/`，plan 正文不动。
- **本机 MySQL `max_connections` 50 → 120**（`deploy/docker-compose.yml`）。plan §9.3 的并发口径是
  "200 请求 / 50 并发"，50 条线程连接 + 主连接会顶到 50 的上限，报 `(1040, 'Too many connections')`。
  生产 compose 仍保持 50（2 vCPU / 1.6 GiB 的预算），CI 用镜像默认 151；三处数值在 phase4 证据里分别写明。
- **B 的重试预算仍是 3 次**（plan §6.2 的初始值），但报告里额外跑了一组"10 次重试"作对照：
  3 次在 50 并发热点下成交率过低，没有这组对照，读者无法判断"卖不完"是方案问题还是预算问题。

## D-007 compose 的备份与替换移入部署脚本（2026-11-14）

- **CI 不再 `cp` compose**。之前 CI 在调用 `deploy.sh` 之前就把 `.docker-compose.prod.new.yml`
  覆盖成 `docker-compose.yml`，脚本再备份也只会备份到新文件；回滚又只改 `IMAGE_TAG`，
  于是"新 compose 本身有问题"时，回滚会拿坏配置把旧镜像再起一遍（外部审查 R6）。
  现在 CI 只上传新文件，`deploy.sh` 在预检通过后 `swap_compose`：校验新文件 →
  `cp -p docker-compose.yml docker-compose.yml.bak` → 替换；`rollback()` 第一步 `restore_compose`，
  迁移失败、起栈失败、健康检查失败三条分支都同时还原 compose 与 tag。
- **C4 的失败分支按 D-004 落地**。AGENTS 里还留着"停 commerce → 起 grounded"的旧流程，
  现在写成实际实现：回滚到上一版镜像与 compose → 验证健康 → 仍不健康就停下报错交人工。
  plan §10.2 与 §11 的 S2/S7 门槛同步去掉"切回 grounded"，改为"让出 8080 不再启回"。

## D-008 关单异常后的恢复机制写准（2026-11-14）

- **删除"DB 连接类异常有限重试并指数退避"**。plan §7.1 原来这么写，但 `tasks.py` 从未配过
  `autoretry_for`；实际加载的 Celery 5.7.0 属性是 `acks_late=True`、
  `acks_on_failure_or_timeout=True`、`reject_on_worker_lost=True`、`autoretry_for=[]`。
  `acks_late` 与 `reject_on_worker_lost` 只覆盖"worker 丢失"，普通任务异常仍走确认分支，不重新入队。
  现在 plan 与 phase5 都写成：任务异常不重投，恢复靠下一拍 beat 重新扫到仍未关闭的订单；
  phase5 末尾加了勘误段落，原始实验输出未改。
- **不因此改成有界重试**。这是取舍：关单是分钟级扫描，补扫天然幂等，多一条重试路径就多一处不确定。
  真要加必须有界、只针对特定异常，并单独验证。

## D-009 二期范围：从"能证明"扩到"像个店"（2026-11-20）

- **之前**：§1.3 明确不做注册、购物车、地址簿、物流、限流、退款售后、前端主题；§11 只到 S8；
  README §11 同样把这些写成"不做"。一期的定位是"只做三件事能被证明"。
- **现在**：新增 §13「二期：从能跑到像个店」，阶段 S9–S14，纳入：
  注册、购物车、地址簿、物流时间线（mock）、限流、退款（mock 整单退）、前端主题、
  商品分类与商品图（SVG 静态）、评论评分、运营后台定制、对账看板、一键脚本。
- **为什么**：一期交付并终审通过后，用户的实际判断是"站点太简易单调"，目标是**看起来像主流购物平台**。
  这是**扩展演示面与业务闭环**，不是补做一期——一期交付时的范围与结论仍然成立。
- **影响**：
  - §1.3 的"不做"清单缩小到：短信、第三方登录、真实支付通道、图片上传、ES、优惠券引擎、
    自定义业务后台、Redis 页面缓存、监控告警、Flower、前端 TS、移动端响应式、骨架屏、
    覆盖率门槛、K8s、微服务、TCC/Saga、分布式锁、AI；
  - §11 增加 S9–S14 六行；§12"范围膨胀"的控制改为"二期单独立项 + 一期 118 用例不许删"；
  - 新建 `docs/candidates.md`（只追加的候选池）；二期记录从 `phase9.md` 开始；
  - `README.md` 的**事实性条目**（§11 不做清单、接口表、首屏数字）在**每个阶段合回 main 时同步微调**，
    不留到最后；**结构性大改（目录、图、章节顺序、首屏定位）留到二期结束（S14 之后）统一重写**。
    理由：S9 一上线注册，README 还写"不做注册"就是假话；但整篇重写会反复返工，不如等形态稳定。
- **不变的底线**：技术栈、部署方式（单机 Compose + ACR + ssh）、CI 结构、并发正确性口径；
  一期 118 个用例一个不许删；注释密度 ≤5%；新增功能必须带用例。

## D-010 限流、公开看板与后台访问（2026-11-20）

- **之前**：§1.3 写"不做限流"；`/admin/` 只允许 127.0.0.1 与内网（C1），公网 404；
  没有任何面向访客的运营/数据页面。
- **现在**：
  - **限流只加在身份写接口**：注册 10 次/小时/IP，登录 30 次/分钟/IP + 5 次/分钟/用户名；
    用 Django + Redis 实现并写测试。浏览、下单、领券**不限**。
  - **`/audit` 对账看板免登录只读**，只展示 SKU 维度聚合（初始/已售/回补/账面/明细合计、
    券发放与使用、订单状态计数），不含用户名与手机号；它是"库存守恒"的可视化证据。
  - **后台仍不暴露公网**：`/admin/` 保持 404（C1 不变）；管理员通过
    `ssh -N -L 8080:127.0.0.1:8080 aliyun` 隧道访问，命令写进 `ops/demo-account.md`。
  - **后台静态资源**用 whitenoise 发，nginx 增加 `location /static/ { proxy_pass http://api:8000; }`。
  - **后台对订单与券只读**：所有状态变更仍须走接口的条件更新，后台不得开后门。
- **为什么**：公开演示站需要挡批量注册，但全站限流会误伤正常浏览；看板的价值在于"任何人点开
  就能看到账是平的"，藏进内网等于没有；`/admin/` 不开放是因为它绕过状态机，风险高于收益。
- **风险**：限流按 IP，NAT 后的多人共用一个出口——所以注册取宽松值 10 次/小时，不做全站限流。

## D-011 详情页两个入口、结算两种来源（2026-11-20，用户拍板）

- **之前**：§11 的 S10 写"结算改为从购物车下单"，含义是详情页的"立即下单"被购物车取代。
- **现在**：详情页**并列两个按钮**——「加入购物车」与「立即购买」；`POST /orders` 同时接受两种来源：
  - 「立即购买」传 `items: [{sku_id, qty}]`（与一期一致）；
  - 购物车结算传 `from_cart: true`，服务端读本人的车，下单成功后整车清空。
  - 两者共用同一个 `client_token` 幂等机制；**重放不清车**，否则会误删重放之后新加的商品。
- **为什么**：主流电商都是两个入口；只留购物车会让"买一件"多两步，而只留立即购买则购物车没意义。
  代价是结算页要能区分来源，且 `items` 与 `from_cart` 互斥（两个都传返回 400）。
- **表**：`cart_item` 独立成 `cart` app，唯一约束 `user + sku`，`qty` 有 `>= 1` 的 CHECK；
  购物车**不存价格**，展示与结算一律取 `SKU.price`。

## D-012 下单必带地址、评价批量提交（2026-11-21）

- **之前**：`POST /orders` 的 `address_id` 可选（S11 为了不改一期 152 个用例的夹具）；
  `POST /orders/{order_no}/review` 按单数命名，含义是"一次评一条明细"。
- **现在**：
  - `address_id` 在**接口层必填**，缺了返回 400；`create_order` 服务层仍允许 `address=None`，
    只给内部直接建单留口子（测试与后续 seed 用）。前端本来就强制选地址，这次是把后端的口子堵上。
  - 评价接口仍是 `POST /orders/{order_no}/review`，但**请求体是数组**，
    一批明细一次提交、整批原子。路径不变，只是体从单条变成列表。
- **为什么**：没有地址的订单在演示里是废单，接口不该允许；评价让用户一条一条提交会做出
  "评了两个失败一个"的半截状态，批量 + 事务更简单也更一致。

## D-013 购物车逐行勾选（2026-11-21）

- **之前**：`from_cart` 结算整辆车。
- **现在**：`cart_item.selected` 存在服务端；`from_cart` 只结算勾中的行，下单成功也只清这些行；
  `PATCH /cart/items` 做全选/取消全选；快照多出 `selected_qty` / `selected_amount`。
- **为什么**：主流电商都允许只结算勾中的商品。勾选状态存服务端而不是前端内存，
  是为了换设备、刷新页面后与上次一致。
- **边界**：下架的行**允许取消勾选但禁止改数量**，否则一条下架商品会把结算永久卡死。






