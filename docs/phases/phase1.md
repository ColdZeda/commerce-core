# phase1 — S1 商品/SKU

> 阶段号与 `docs/plan.md` §11 的 S1 对应。阶段结束封口，不再追加；新内容进 phase2。

## 目标

把六张业务表落成真实 schema，并让商品/SKU 能被查询和维护。本阶段**不做**下单、领券、登录。

## 范围（plan §11 S1）

- 六张表模型与迁移：`product`、`sku`、`coupon`、`user_coupon`、`order`、`order_item`
  （对应 app：`catalog` / `promotion` / `trade`）
- admin：商品 + SKU 内联，可改价格与库存
- `GET /api/v1/products`：分页、keyword、排序白名单、最低 SKU 价
- `GET /api/v1/products/{id}`：商品与在售 SKU/库存，404 走统一错误体
- `seed_demo` 管理命令（幂等）
- 索引与查询次数检查（`assertNumQueries`）

## 明确不做

- 登录/JWT、券列表/领取、订单接口（S2、S3）
- 任何库存扣减、锁、事务边界（S3）
- 前端商品页：`/products`、`/products/:id` 按 plan §8 在 S3 与四页一起落地
- 券的三处 UI 入口（S2）

## 门槛（全部满足才算完成）

- [x] 商品可浏览：两个接口按契约返回，金额是字符串、时间是 ISO8601
- [x] 分页/筛选正确：`page_size` 默认 10、上限 50；keyword 命中 name/subtitle；排序白名单外 400
- [x] 迁移可重复执行：`migrate` 连续两次无副作用，`makemigrations --check` 无待生成
- [x] 列表无 N+1：列表 2 条 SQL、详情 2 条 SQL，用 `assertNumQueries` 断言
- [x] admin 可维护价格库存：改价格/库存后数据库生效

## 实施顺序

1. 建 app 与共享时间戳基类 → 6 个模型 → 迁移 → `SHOW CREATE TABLE` 核对索引与 CHECK
2. admin（Product + SKU inline）
3. 统一错误体 + 分页 + 两个只读接口
4. `seed_demo`
5. 测试：约束、接口契约、查询次数、admin 保存
6. 证据回填、`STATUS.md`、提交与推送

## 证据

### E1 六张表的真实 DDL（MySQL 8.0.43，`SHOW CREATE TABLE` 摘录）

```text
product     KEY idx_product_active_id (is_active, id DESC)
sku         UNIQUE KEY sku_code; KEY sku_product_id_... (product_id);
            CONSTRAINT ck_sku_stock_non_negative CHECK (stock >= 0)
coupon      KEY idx_coupon_active_end (is_active, end_at);
            CONSTRAINT ck_coupon_issued_within_total CHECK ((issued_qty >= 0) and (issued_qty <= total_qty))
user_coupon UNIQUE KEY uq_user_coupon_user_coupon (user_id, coupon_id);
            KEY idx_user_coupon_user_status (user_id, status)
order       UNIQUE KEY order_no; UNIQUE KEY uq_order_user_client_token (user_id, client_token);
            KEY idx_order_user_created (user_id, created_at DESC);
            KEY idx_order_status_expire (status, expire_at)
order_item  KEY order_item_order_id_... (order_id); KEY order_item_sku_id_... (sku_id);
            CONSTRAINT ck_order_item_qty_positive CHECK (qty > 0)
```

全部 `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci`。FK 删除策略按 plan §3.2：
`order_item→order CASCADE`、`order_item→sku SET_NULL`、`order→user PROTECT`、
`order→user_coupon SET_NULL`、`sku→product PROTECT`、`user_coupon→coupon/user PROTECT`。

`order` 是 MySQL 保留字，表名沿用 plan；Django 会给标识符加反引号，用 ORM 和迁移都没问题，
但手写 SQL 必须自己转义（已记进 `docs/plan-changes.md` D-003）。

### E2 迁移可重复执行

```text
python manage.py migrate                  → Applying catalog.0001_initial / promotion.0001_initial /
                                            trade.0001_initial ... OK
python manage.py migrate（第二次）        → No migrations to apply.
python manage.py makemigrations --check   → No changes detected
```

### E3 接口契约（本机 runserver + seed 数据，实测输出）

```text
GET /api/v1/products
→ 200 {"count":6,"next":null,"previous":null,"results":[
     {"id":6,"name":"桌面显示器支架","min_price":"259.00","created_at":"2026-11-10T20:14:46.759260+08:00"}, ...]}

GET /api/v1/products?page=2&page_size=2
→ 200 {"count":6,"next":"...page=3&page_size=2","previous":"...page_size=2","results":[2 条]}

GET /api/v1/products?keyword=键盘
→ 200 {"count":1,"results":[{"name":"机械键盘 87 键","min_price":"289.00"}]}

GET /api/v1/products?ordering=price&page_size=3
→ 200 依次 99.00 / 219.00 / 259.00（按最低在售价升序）

GET /api/v1/products?ordering=name
→ 400 {"code":"VALIDATION_ERROR","message":"请求参数不合法",
       "detail":{"ordering":["允许的排序字段：-created_at, -price, created_at, price"]}}

GET /api/v1/products/1
→ 200 {"id":1,"name":"降噪蓝牙耳机","min_price":"399.00",
       "skus":[{"sku_code":"EAR-100","price":"399.00","stock":120},
               {"sku_code":"EAR-100-PRO","price":"599.00","stock":40}], ...}

GET /api/v1/products/999999
→ 404 {"code":"NOT_FOUND","message":"商品不存在"}
```

金额一律字符串（DRF `COERCE_DECIMAL_TO_STRING`），时间带时区偏移 `+08:00`。
下架商品不出现在列表，也不可访问详情（404）；详情只带在售 SKU。

### E4 查询次数（`assertNumQueries`，15 个用例全过）

```text
test_list_query_count_stays_constant      → 12 商品 × 2 SKU，列表固定 2 条 SQL（count + 带 Min 的页查询）
test_detail_query_count_stays_constant    → 3 SKU 的详情固定 2 条 SQL（商品 + prefetch 在售 SKU）
```

最低价用 `Min("skus__price", filter=Q(skus__is_active=True))` 在 SQL 里算，不在 Python 里循环；
详情的 `min_price` 复用已 prefetch 的 `active_skus`，不再补一条聚合查询。

### E5 admin 可维护价格库存

`test_admin_can_update_sku_price_and_stock`：登录 admin → GET 商品编辑页 200 →
POST 内联表单把 SKU 价格改 `168.00`、库存改 `3` → 302 且 `refresh_from_db()` 后两值生效。

### E6 seed 幂等

```text
python manage.py seed_demo        → 新增商品 6 个、SKU 9 个；当前商品 6 个、SKU 9 个
python manage.py seed_demo（再跑）→ 新增商品 0 个、SKU 0 个；当前商品 6 个、SKU 9 个
```

`get_or_create` 只补缺，不覆盖已有价格/库存，重跑不会把演示数据重置。

### E7 本机检查

```text
pytest                                     → 15 passed（catalog 12 + health 3）
ruff check . / ruff format --check .        → 全过
python scripts/check_comments.py backend    → 注释行 12 / 代码行 752，占比 1.6%，OK
```

### E8 容器内同样可用

重建 `commerce-core-api:s0`（复用构建缓存）后重启 `commerce-api`：
`/api/v1/health` 200，`/api/v1/products` 返回同样的 6 条数据。
