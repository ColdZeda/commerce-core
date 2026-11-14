# STATUS

> 更新于 2026-11-14（外部审查终审通过，项目收口）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S8 全部完成，外部审查也已收口。** 业务闭环在公网跑通，CI/CD 与回滚都演练过；
另经一次独立审查（R1–R10）与一轮终审，全部通过。README 可以直接给外部看。

- 公网：`http://120.24.67.82:8080`（无域名无 HTTPS，端口 8080）
- 线上版本：审查修复自 **`d1cf930`** 起（其后都只有文档提交）；实际 tip 看服务器 `.current_tag`
- 服务器 6 个容器：api(healthy) / web / worker / beat / mysql(healthy) / redis(healthy)
- 内存实测 available **761 MB**，容器合计约 413 MiB，未触发降级
- 测试：**118 个用例**全过；注释密度 1.9%；CI 全绿
- 终审：审查方对 `4ec7f93` 复核 R1–R10 与上线时补的 `d1cf930`，**全部通过**；
  118 个原有用例 + 29 个额外验收用例通过，无阻塞项

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

**已收口，没有下一步。** 按终审结论，不再扩审、不再优化、不再追加修改。

留档位置：修复是四批提交（`cd3b86c` → `d1cf930`），每批的改动、回归与反向验证在
`..\check\FIX-01.md` … `FIX-04.md`；审查与两轮回应的全过程在 `..\check\README.md`。
想看"改了什么"就直接看这五个文件，不用翻 git log。

## 卡点

无。

## 已知边界（有意保留，不是待办）

- **回滚在"compose 真有差异"时没实测**：修完那次相邻两版 `docker-compose.prod.yml` 内容相同，
  所以 `.bak` 与当前文件一致，"回滚拿回旧配置"只有离线模拟证据（`..\check\sim_deploy\`）
- `mode=check` 的只读行为只有本地片段模拟（`..\check\sim_ci\`）与一次真机 deploy 的旁证
- `PAY_CALLBACK_SECRET` 在服务器 `.env` 里为空，回调签名复用 `SECRET_KEY`（功能已实测，安全上不理想）
- Django admin 的 `/static/` 没托管：内网能开页面但没有样式，业务验收不依赖它
- 无 HTTPS / 无域名，公网明文；`ENABLE_MOCK_PAY=true` 意味着任何登录用户能把自己的订单标成已支付
- 自动回滚只在"本次部署失败"时触发，不处理"上线后才发现业务问题"

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → `README.md`（对外交付物）；
   要看审查过程与修复记录，读 `..\check\README.md`（索引）与 `..\check\FIX-0N.md`
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. **部署**：push 到 main 自动部署；只看不动用 GitHub Actions → Run workflow → mode `check`
4. **回滚**：`ssh aliyun` → `cd /opt/commerce-core && ./deploy.sh <旧 sha>`
5. 推 GitHub 偶发 reset，必要时带代理 `-c http.proxy=http://127.0.0.1:10808`；
   GitHub API 未认证只有 60 次/小时，脚本里用 `git credential fill` 取 token
6. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`（需要 Docker 里的 MySQL/Redis）；
   前端 `cd frontend && npm run dev`
7. 踩过的坑：只重建 api 不重建 web 会 502；`docker compose run` 无 TTY 要 `-T`；
   Actions 里步骤 skipped 不会让 job 变红；PowerShell 5.1 吃引号，远端脚本要上传 `.sh` 再执行
