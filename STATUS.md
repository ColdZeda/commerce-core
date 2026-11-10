# STATUS

> 更新于 2026-11-10。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

S0 骨架已建（目录、AGENTS、plan、phase0、注释检查脚本），**尚未开始编码**。

## 下一步

按 `docs/phases/phase0.md` 执行 S0：
官方骨架 → MySQL/Redis compose → `/health` → 依赖锁定 → Windows 连库 → Linux 镜像 uWSGI 实测 → CI 初线。

## 卡点

无。

## 未验证（不许当成已完成）

- GitHub 仓库 `commerce-core` 是否已建、远程 URL、默认分支
- 阿里云 ACR 地址、命名空间、凭据提供方式
- SSH 主机／端口／用户／密钥
- 本机 Windows／Python 实际版本、`pip freeze`、Docker 镜像与磁盘余量
- 本机是否已拉 `mysql:8` / `redis:7`，是否需要镜像加速
- `mysqlclient` 对锁定版本／Python／架构是否有 wheel（用 `pip download --only-binary` 判定）
- SWAS 当前内存、swap、磁盘、Docker／Compose 版本、容器、端口、防火墙
- grounded-qa 的实际 compose project、路径、启停命令、数据卷、备份位置
- PyCharm 版本；WSL2 是否可用
- 公网 demo 用户的安全初始化方式
- 8080 端口是否真空闲
