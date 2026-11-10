# STATUS

> 更新于 2026-11-10（S1 收口）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S1 完成**：六张业务表已落库（catalog / promotion / trade），商品列表与详情两个接口、admin 改价改库存、
`seed_demo`、查询次数断言都在。证据见 `docs/phases/phase1.md`。
两端仓库（`github.com/ColdZeda/commerce-core`、`gitee.com/ColdZeda/commerce-core`）同步 `main`；
推 GitHub 要带本机代理，推 Gitee 直连，命令见 `AGENTS.md` §2。

## 下一步

S2：JWT `login/refresh/me`、券列表/领取/我的券、领券并发约束、前端登录与券入口、401 单飞；
外加服务器最小栈（mysql/api/nginx）冒烟与 grounded-qa 往返切换。

## 卡点

- S2 的服务器部分要用户先给：SSH 主机/端口/用户/密钥，SWAS 控制台 8080 是否放行，
  grounded-qa 的 compose 路径与启停命令。没有这些只能先做纯本地部分。

## 未验证（不许当成已完成）

- 服务器侧一切：内存/swap/磁盘、Docker 与 Compose 版本、端口占用、防火墙、grounded-qa 现状
- 阿里云 ACR 地址/命名空间/凭据（S7）
- 前端商品页与四路由（S3 一起做）
- 任何库存扣减、锁、并发（S3/S4）
- 券领取并发、订单幂等（S2/S3）
- 公网 demo 用户的安全初始化方式
