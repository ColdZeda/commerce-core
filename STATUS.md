# STATUS

> 更新于 2026-11-13（S8 收尾完成）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S8 全部完成**。业务闭环在公网跑通，CI/CD 与回滚都演练过，README 可以直接给外部看。

- 公网：`http://120.24.67.82:8080`（无域名无 HTTPS，端口 8080）
- 线上版本：**`8339217`**（`.current_tag`），上一版 `31f1791`（`.previous_tag`，可回滚）
- 服务器 6 个容器：api(healthy) / web / worker / beat / mysql(healthy) / redis(healthy)
- 内存实测 available **759 MB**，容器合计约 413 MiB，未触发降级
- 测试：**103 个用例**全过；注释密度 1.8%；CI 全绿

**S8 做的三件事**：

1. **README 重写**：定位、线上事实、链路与状态机、设计取舍、A/B/C 实测表、14 个接口、
   本地运行、测试与 CI、部署与回滚、目录、踩过的坑、边界与非目标、常见追问
2. **演示账号命令** `create_demo_user`：口令来自 `DEMO_PASSWORD` 或随机生成且只打印一次，
   幂等（已存在则跳过，`--reset` 才改），4 个用例覆盖
3. **AGENTS/阶段文档跟上实际状态**
4. **公网回调验收**（2026-11-14）：用服务器密钥在容器内签名，从开发机打公网入口，
   6 种场景全过——正确签名 200、重放幂等且 `paid_at` 不变、篡改签名/金额 401、
   超窗 401、已取消订单 409 且状态不被改回（`docs/phases/phase8.md` §7）
5. **README 增加"项目文档"索引**：把 plan / plan-changes / phases / STATUS 链进去，
   并列出几条真实返工，让施工过程可被检查

阶段记录：`docs/phases/phase0.md` … `phase8.md`。

## 下一步

**项目交付完毕。** 想继续的话：

1. 域名 + HTTPS（现在明文 8080）；需要外部可点链接时再考虑
2. `.env` 里补 `PAY_CALLBACK_SECRET`（现在回落 `SECRET_KEY`）

## 卡点

无。

## 未验证（不许当成已完成）

- `PAY_CALLBACK_SECRET` 在服务器 `.env` 里为空，回调签名复用 `SECRET_KEY`（功能已实测，安全上不理想）
- Django admin 的 `/static/` 没托管：内网能开页面但没有样式，业务验收不依赖它
- 无 HTTPS / 无域名，公网明文；`ENABLE_MOCK_PAY=true` 意味着任何登录用户能把自己的订单标成已支付
- 自动回滚只在"本次部署失败"时触发，不处理"上线后才发现业务问题"

> 已消除：README 的本地运行已在开发机上按原文走通（103 用例全过，前端与 Celery 都起得来），
> 公网演示账号 `demo` / `demo1234` 已创建并验证。

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
