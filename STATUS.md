# STATUS

> 更新于 2026-11-10（S0 收口）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0 完成并已推送**：`github.com/ColdZeda/commerce-core`，`main` 已推到远程，CI 首次运行即绿
（run #1，46s，lint + test 全过），收口提交打了 annotated tag `s0`。
证据见 `docs/phases/phase0.md`（E1–E12）。

## 下一步

等用户确认后进 S1：六表模型与迁移、admin、商品列表/详情、seed、索引与查询检查（含 assertNumQueries）。

## 卡点

无。

## 未验证（不许当成已完成）

- 阿里云 ACR 地址、命名空间、凭据提供方式
- SSH 主机／端口／用户／密钥
- SWAS 当前内存、swap、磁盘、Docker／Compose 版本、容器、端口、防火墙
- grounded-qa 的实际 compose project、路径、启停命令、数据卷、备份位置
- 8080 端口是否真空闲；服务器上 1.6GiB 内存是否够 plan §10.3 的初始预算
- 镜像在 CI 里构建的耗时（S0 的 CI 不建镜像；本机首次构建约 35 分钟，卡在 apt 下载）
- WSL2 是否可用（S7 全栈预演要用）
- 公网 demo 用户的安全初始化方式
