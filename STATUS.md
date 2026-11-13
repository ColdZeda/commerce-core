# STATUS

> 更新于 2026-11-13（S8 收尾完成）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S8 全部完成**。业务闭环在公网跑通，CI/CD 与回滚都演练过，README 可以直接给外部看。

- 公网：`http://120.24.67.82:8080`（无域名无 HTTPS，端口 8080）
- 线上版本：**`e74a682`**（`.current_tag`），上一版 `d18ff16`（`.previous_tag`，可回滚）
- 服务器 6 个容器：api(healthy) / web / worker / beat / mysql(healthy) / redis(healthy)
- 内存实测 available **759 MB**，容器合计约 413 MiB，未触发降级
- 测试：**103 个用例**全过；注释密度 1.8%；CI 全绿

**S8 做的三件事**：

1. **README 重写**：定位、线上事实、链路与状态机、设计取舍、A/B/C 实测表、14 个接口、
   本地运行、测试与 CI、部署与回滚、目录、踩过的坑、边界与非目标、常见追问
2. **演示账号命令** `create_demo_user`：口令来自 `DEMO_PASSWORD` 或随机生成且只打印一次，
   幂等（已存在则跳过，`--reset` 才改），4 个用例覆盖
3. **AGENTS/阶段文档跟上实际状态**

阶段记录：`docs/phases/phase0.md` … `phase8.md`。

## 下一步

**项目交付完毕，没有指定的下一阶段。** 想继续的话，按价值排序：

1. **公网演示账号**：`ssh aliyun` → `cd /opt/commerce-core && docker compose exec -T api python manage.py create_demo_user`
   （随机口令只打印一次；想自己定就给 `DEMO_PASSWORD` 加 `--reset`）——不做也行，README 已写明做法
2. 在干净机器上按 README 从零跑一遍（本阶段没做，见"未验证"）
3. 需要外部可点的演示时，再考虑域名 + HTTPS（目前是明文 8080）

## 卡点

无。

## 未验证（不许当成已完成）

- **README 的"本地运行"没在干净机器上从零复现**：开发机当时 Docker 没起，命令是对着现有配置核对的
- 公网演示账号还没建（命令可用，口令未定）
- `PAY_CALLBACK_SECRET` 在服务器 `.env` 里为空，回调签名回落到 `SECRET_KEY`
- Django admin 的 `/static/` 没托管：内网能开页面但没样式，业务验收不依赖它
- 无 HTTPS / 无域名，公网明文；`ENABLE_MOCK_PAY=true` 意味着任何登录用户能把自己的订单标成已支付
- 自动回滚只在"本次部署失败"时触发，不处理"上线后才发现业务问题"

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → `README.md`（对外交付物）
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. **部署**：push 到 main 自动部署；只看不动用 GitHub Actions → Run workflow → mode `check`
4. **回滚**：`ssh aliyun` → `cd /opt/commerce-core && ./deploy.sh <旧 sha>`
5. 推 GitHub 偶发 reset，必要时带代理 `-c http.proxy=http://127.0.0.1:10808`；
   GitHub API 未认证只有 60 次/小时，脚本里用 `git credential fill` 取 token
6. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`（需要 Docker 里的 MySQL/Redis）；
   前端 `cd frontend && npm run dev`
7. 踩过的坑：只重建 api 不重建 web 会 502；`docker compose run` 无 TTY 要 `-T`；
   Actions 里步骤 skipped 不会让 job 变红；PowerShell 5.1 吃引号，远端脚本要上传 `.sh` 再执行
