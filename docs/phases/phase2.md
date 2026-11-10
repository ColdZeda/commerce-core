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

- [ ] 重复领券 / 超发返回正确业务码：`COUPON_ALREADY_CLAIMED`、`COUPON_SOLD_OUT`，不能是 500
- [ ] 刷新页面不掉登录：`/auth/me` 能恢复会话
- [ ] 并发领券测试通过（真实 MySQL，独立线程连接），`issued_qty` 不超 `total_qty`
- [ ] 停 grounded-qa → 起 commerce 最小栈 → 外网可达 → 记录内存实测
      （原计划"再切回 grounded"按用户 2026-11-10 的决定取消，见 `docs/plan-changes.md` D-004）
- [ ] 不测尚未完成的下单

## 实施顺序

1. `accounts` + JWT 三接口 + 401 错误码区分
2. 券三个接口 + 领券事务 + 并发测试
3. 前端登录、auth store、401 单飞、领券入口
4. 服务器最小栈与公网冒烟（先贴命令再执行，流水进 `ops/server-log.md`）
5. 证据回填、`STATUS.md`、推送

## 证据

（完成后追加）
