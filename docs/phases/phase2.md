# phase2 — S2 登录/券 + 公网冒烟

> 阶段号与 `docs/plan.md` §11 的 S2 对应。阶段结束封口，不再追加；新内容进 phase3。

## 目标

把"谁能下单、券怎么拿到手"这条链路打通，并把最小栈真正放到服务器上验证一次外网可达。

## 范围

- `accounts` app：`POST /auth/login`、`POST /auth/refresh`、`GET /auth/me`；
  Bearer 认证，401 区分 `TOKEN_EXPIRED` 与 `TOKEN_INVALID`
- 券：`GET /coupons`（匿名可看，登录时带 `claimed`）、`POST /coupons/{id}/claim`（201 / 409 业务码）、
  `GET /me/coupons?status=unused|used|expired`
- 领券并发：事务内条件增加 `issued_qty` → 检查 rowcount → 建 `user_coupon`
- 前端：`/login`、auth store（localStorage）、axios 拦截器 + 401 单飞刷新、`/products` 的领券入口
- 服务器：`/opt/commerce-core` 最小栈（mysql + api + nginx），外网 `8080` 验证，记录内存

## 明确不做

- 下单、订单、支付、关单（S3/S5/S6）
- 库存扣减与锁（S3）
- 完整优惠券引擎（只有固定满减，不叠加、不续期）

## 门槛

- [x] 重复领券 / 超发返回正确业务码：`COUPON_ALREADY_CLAIMED`、`COUPON_SOLD_OUT`，不能是 500
- [x] 刷新页面不掉登录：`/auth/me` 能恢复会话
- [x] 并发领券测试通过（真实 MySQL，独立线程连接），`issued_qty` 不超 `total_qty`
- [ ] 停 grounded-qa → 起 commerce 最小栈 → 外网可达 → 记录内存实测
      （原计划"再切回 grounded"按用户 2026-11-10 的决定取消，见 `docs/plan-changes.md` D-004）
- [x] 不测尚未完成的下单

> 服务器那一项还没做：需要用户先在本机 `docker login` ACR，再按 `ops/runbook.md` 的流程停 grounded-qa。
> 在它完成之前本阶段不算收口。

## 实施顺序

1. `accounts` + JWT 三接口 + 401 错误码区分
2. 券三个接口 + 领券事务 + 并发测试
3. 前端登录、auth store、401 单飞、领券入口
4. 服务器最小栈与公网冒烟（先贴命令再执行，流水进 `ops/server-log.md`）
5. 证据回填、`STATUS.md`、推送

## 证据

### E1 登录/刷新/me（8 个用例）

```text
POST /auth/login     → 200 {access, refresh, user:{id, username, is_staff}}
                     密码错 → 401 AUTH_INVALID_CREDENTIALS
POST /auth/refresh   → 200 {access}；refresh 过期 → 401 TOKEN_EXPIRED
GET  /auth/me        → 无 token / 伪造 token → 401 TOKEN_INVALID
                     过期 token → 401 TOKEN_EXPIRED
                     有效 token → 200
```

`accounts/tokens.py` 负责区分：能解析但 `exp` 已过 → `TOKEN_EXPIRED`；解析不了或验签失败 → `TOKEN_INVALID`。
access 默认 15 分钟（`JWT_ACCESS_MINUTES` 可覆盖），refresh 7 天，不轮换、不启用 blacklist。

### E2 券接口（8 个用例）

```text
GET  /coupons                 → 只返回 is_active 且在有效期内的券；登录时 claimed 正确
POST /coupons/{id}/claim      → 201；issued_qty +1
                              重复领取 → 409 COUPON_ALREADY_CLAIMED（名额不重复消耗）
                              已抢光   → 409 COUPON_SOLD_OUT
                              过期/下架 → 409 COUPON_NOT_USABLE
                              未登录   → 401 TOKEN_INVALID
GET  /me/coupons?status=...   → unused / used / expired 三种筛选；非法值 → 400 VALIDATION_ERROR
```

### E3 并发领券（真实 MySQL，12 线程抢 5 个名额）

```text
test_concurrent_claims_never_exceed_total_qty
→ 成功 5 次、COUPON_SOLD_OUT 7 次
→ coupon.issued_qty == 5，user_coupon 行数 == 5
```

名额靠 `UPDATE coupon SET issued_qty = issued_qty + 1 WHERE id=? AND issued_qty < total_qty` 的 rowcount；
同一用户并发重复领由 `uq_user_coupon_user_coupon` 兜住，并把已加的名额随事务回滚。

### E4 前端手工清单（浏览器实测）

| 步骤 | 结果 |
|---|---|
| 匿名打开 `/products` | 6 个商品 + 3 张券渲染正常，按钮为「领取」 |
| 匿名点「领取」 | 跳转 `/login?redirect=/products` |
| 用本地演示用户登录 | 回到 `/products`，header 显示用户名 |
| 点「领取」 | 按钮变「已领取」并禁用，剩余张数 50 → 49 |
| 刷新页面 | 仍是登录态（`/auth/me` 恢复），已领取状态保持 |

**401 单飞**：把 access 寿命临时调到 3 秒（`JWT_ACCESS_MINUTES=0.05`）后重新登录，等过期再点「领取」，
服务端日志正好是"一次 401 → 一次 refresh → 同一个请求重试成功"：

```text
POST /api/v1/coupons/2/claim HTTP/1.1" 401
POST /api/v1/auth/refresh    HTTP/1.1" 200
POST /api/v1/coupons/2/claim HTTP/1.1" 201
```

前端侧：并发 401 共用同一个 `refreshPromise`，登录/刷新自身与已重试过的请求不再触发刷新。

### E5 本机检查

```text
pytest                         → 32 passed（health 3 + catalog 12 + accounts 8 + promotion 9）
ruff check / format --check     → 全过
python scripts/check_lock.py    → lock=21 installed=21，一致
npm run lint                    → 0 warning
npm run build                   → 成功
```

容器内同样验证：重建镜像后 `/api/v1/health` 200、`/api/v1/coupons` 返回 3 张券、登录 200。

本地演示用户 `demo` 只存在于开发库（`seed_demo` 不建用户），公网 demo 用户的初始化方式留给 S8。
