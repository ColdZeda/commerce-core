# STATUS

> 更新于 2026-11-14（外部审查四批修复已上线并验证）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S8 全部完成**；业务闭环在公网跑通，CI/CD 与回滚都演练过，README 可以直接给外部看。
另有一次**外部 AI 独立审查**收口，10 项问题全部成立；**四批修复已全部完成、推送并部署**。

- 公网：`http://120.24.67.82:8080`（无域名无 HTTPS，端口 8080）
- 线上版本：**`d1cf930`**（`.current_tag`），上一版 `dd525d2`（`.previous_tag`，可回滚）
- 服务器 6 个容器：api(healthy) / web / worker / beat / mysql(healthy) / redis(healthy)
- 内存实测 available **761 MB**，容器合计约 413 MiB，未触发降级
- 测试：**118 个用例**全过；注释密度 1.9%；CI 全绿

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

**外部审查的修复。** 另一个 AI 独立审查了基线 `73f256c`，提出 R1–R10；
我方逐项复核后**全部成立**（R4 降 P2），两轮已收口。过程与本方最终方案都在仓库外
`..\check\`（入口 `..\check\README.md`，方案见 `..\check\RESPONSE-02.md` §2）。

分四批，一批一提交、一批一验证：

1. **✅ R1–R4 已修**（本地提交，未推送；验证记录 `..\check\FIX-01.md`）：
   `create_order` 在资源校验失败后于**事务外**按 token 回查原单；`run_parallel` 改用
   `future.result()` 收异常并断言结果条数与重放次数；JWT 分类只认验签结论
   （`ExpiredTokenError` 才算过期）；回调 `sign` 限 64 位十六进制，格式错 400、签名错 401。
   回归用例 103 → **118**
2. **✅ R5、R7 已修**（本地提交，未推送；验证记录 `..\check\FIX-02.md`）：
   上传重试耗尽 `exit 1`；预检的 compose 校验 `|| exit 1`（健康与内存只诊断）；
   check 模式不推镜像、不写服务器，compose 语法校验移到 runner 本地
3. **✅ R6 已修**（本地提交，未推送；验证记录 `..\check\FIX-03.md`）：
   CI 不再自己 `cp` compose，改由 `deploy.sh` 校验→备份→替换，回滚时连同 tag 一起还原；
   `AGENTS.md` C4 与 plan 的 grounded 表述按 D-004 改准（新增 D-007 记录）
4. **✅ R8–R10 已修**（验证记录 `..\check\FIX-04.md`）：README 本地步骤补 venv 初始化与
   `create_demo_user`、演示账号注明"仅线上"；关单重投的表述按 Celery 5.7.0 实际属性改准
   （phase5 加勘误、plan 记 D-008）；README 的 `F()` 与 A/B/C 边界两句改正

**四批全部完成并上线**（`d1cf930`）。上线后公网复验了三处修复的实际行为：

- 伪造 token（`exp=[]`）→ **401 `TOKEN_INVALID`**（改前 500）
- 回调 `sign` 传 Unicode → **400 `VALIDATION_ERROR`**（改前 500）
- 回调 `sign` 传 64 位错签名 → **401 `PAY_SIGN_INVALID`**（契约不变）

剩下的是**请审查方只核验修复与关联回归**，不再全文互审。首次推送时 CI 在新增的 compose 校验
步骤失败过一次（服务级 `env_file: .env` 不进仓库），已修（`d1cf930`），见 `..\check\FIX-02.md` §3。

其余可选项（用户已明确跳过）：域名 + HTTPS、`.env` 补 `PAY_CALLBACK_SECRET`。

## 卡点

无。

## 未验证（不许当成已完成）

- **回滚在"compose 真有差异"时还没实测**：本次两个版本的 `docker-compose.prod.yml` 内容相同，
  所以 `docker-compose.yml.bak` 与当前文件一致，"回滚拿回旧配置"只有离线模拟证据
- 改后的 CI 只在一次成功部署里跑通过；`mode=check` 的只读行为仍只有本地片段模拟（`..\check\sim_ci\`）
- `PAY_CALLBACK_SECRET` 在服务器 `.env` 里为空，回调签名复用 `SECRET_KEY`（功能已实测，安全上不理想）
- Django admin 的 `/static/` 没托管：内网能开页面但没有样式，业务验收不依赖它
- 无 HTTPS / 无域名，公网明文；`ENABLE_MOCK_PAY=true` 意味着任何登录用户能把自己的订单标成已支付
- 自动回滚只在"本次部署失败"时触发，不处理"上线后才发现业务问题"

> 已消除：README 的本地运行已在开发机上按原文走通（103 用例全过，前端与 Celery 都起得来），
> 公网演示账号 `demo` / `demo1234` 已创建并验证。

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → `README.md`（对外交付物）；
   若要做审查修复，再读 `..\check\README.md`、`..\check\RESPONSE-02.md` §2，
   以及各批验证记录 `..\check\FIX-0N.md`
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. **部署**：push 到 main 自动部署；只看不动用 GitHub Actions → Run workflow → mode `check`
4. **回滚**：`ssh aliyun` → `cd /opt/commerce-core && ./deploy.sh <旧 sha>`
5. 推 GitHub 偶发 reset，必要时带代理 `-c http.proxy=http://127.0.0.1:10808`；
   GitHub API 未认证只有 60 次/小时，脚本里用 `git credential fill` 取 token
6. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`（需要 Docker 里的 MySQL/Redis）；
   前端 `cd frontend && npm run dev`
7. 踩过的坑：只重建 api 不重建 web 会 502；`docker compose run` 无 TTY 要 `-T`；
   Actions 里步骤 skipped 不会让 job 变红；PowerShell 5.1 吃引号，远端脚本要上传 `.sh` 再执行
