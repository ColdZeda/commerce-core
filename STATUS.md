# STATUS

> 更新于 2026-11-10（S2 进行中）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S2 进行中**：登录（JWT 三接口，401 区分过期/伪造）、券（列表/领取/我的券）、领券并发（12 线程抢 5 名额
不超发）、前端 `/login` + `/products` 领券入口 + 401 单飞刷新，全部本地实测通过，容器里也验过。
证据见 `docs/phases/phase2.md`（E1–E5）。
**只剩服务器最小栈与公网冒烟**（`/opt/commerce-core` + 外网 8080 + 内存实测）。

## 下一步

1. 用户在本机跑一次 `docker login crpi-…cn-shenzhen…`（密码自己输）
2. 本机构建镜像 → 推 `commerce-core/api:<tag>`
3. 服务器：放 compose → 用户填 `/opt/commerce-core/.env` → `compose pull && up -d`
4. 停 grounded-qa（一次性，卷保留，不再启回）→ 外网 `8080/api/v1/health` → 记内存

## 卡点

- 服务器那步需要用户配合：本机 `docker login`、服务器上填 `.env`；停 grounded-qa 前会先贴命令确认。

## 未验证（不许当成已完成）

- 服务器最小栈：`/opt/commerce-core`、外网 8080、容器内存实测
- 阿里云 ACR 首次 push 与服务器 pull（命名空间已建好，仓库靠自动创建）
- 商品详情页、订单页（S3）
- 下单、库存扣减、锁、支付、关单（S3–S6）
- 公网 demo 用户的安全初始化方式（S8）
