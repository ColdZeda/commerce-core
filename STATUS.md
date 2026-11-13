# STATUS

> 更新于 2026-11-13（S7b 完成）。每轮结束、每阶段结束都更新；滚动覆盖，不追加历史。全文件目标：10 秒读完。

## 现在在哪

**S0–S7 全部完成**，业务闭环已经在公网跑起来：
登录 → 领券 → 下单 → 取消 / 超时关单 → 模拟支付。

- 公网地址 `http://120.24.67.82:8080`（无域名无 HTTPS，端口 8080）
- 当前部署：**`4ba508b`**（`.current_tag`），上一版 `fd3b456`（`.previous_tag`，api+web 都在，可回滚）
- 服务器 6 个容器：api(healthy) / web / worker / beat / mysql(healthy) / redis(healthy)
- 内存实测 available **759 MB**，容器合计约 413 MiB，**未触发任何降级**

**S7b 完成的三件事**：

1. **首次部署**（`da630e9`）：迁移先于起栈、nginx 服务被 web 替换、公网三单验收 13/13
2. **回滚演练**：`fd3b456 → da630e9`（26 秒）→ 验公网 → `da630e9 → fd3b456`（28 秒），
   回滚就是同一个 `deploy.sh` 传旧 tag
3. **自动部署**：push 到 main 会走完 lint/test/build/push/deploy 全链路（实测 `4ba508b` 那次 2 分 30 秒）

阶段记录：`docs/phases/phase0.md` … `phase7.md`（S7 已封口）；服务器事实与流水在仓库外
`..\ops\runbook.md` 与 `..\ops\server-log.md`。

## 下一步

**S8 收尾**（`docs/plan.md` §11 的最后一阶段）：

- README 重写：项目定位（项目级实操，不是生产级高并发）、架构、接口契约、状态机、测试与部署方式
- 演示数据与公网 demo 用户的安全初始化方式（现在只能靠脚本临时建，还没定方案）
- 把压测与 A/B/C 实验的实测数字整理成可引用的一节
- 取舍与失败记录：假绿那次（skipped 步骤）、ACR attestation、nginx 缓存上游 IP、内存预算
- 面试讲述材料与四格表

## 卡点

无。

## 未验证（不许当成已完成）

- `PAY_CALLBACK_SECRET` 在服务器 `.env` 里为空，回调签名回落到 `SECRET_KEY`；
  `/payments/callback` 只有测试覆盖过，公网没有真实支付通道
- Django admin 的 `/static/` 没托管：内网能开页面但没有样式，业务验收不依赖它
- 公网 demo 用户还没有正式方案（S8）
- 无 HTTPS / 无域名，公网明文；`ENABLE_MOCK_PAY=true` 意味着任何登录用户都能把订单标成已支付
- 自动回滚只在"本次部署失败"时触发，不处理"上线后才发现业务问题"——那种要人工 `./deploy.sh <旧 tag>`

## 接手提示（新会话读到这里就够）

1. 先读 `AGENTS.md` → 本文件 → `docs/phases/phase7.md`
2. 动服务器前读 `..\ops\runbook.md`；每次服务器操作追加到 `..\ops\server-log.md`
3. **部署**：push 到 main 自动部署；想只看不动，就 GitHub Actions → Run workflow → mode 选 `check`
4. **回滚**：`ssh aliyun` 后 `cd /opt/commerce-core && ./deploy.sh <旧 sha>`（先确认 ACR 里 api+web 都在）
5. 推 GitHub 偶发 reset；必要时带代理 `-c http.proxy=http://127.0.0.1:10808`。
   GitHub API 未认证只有 60 次/小时，脚本里要用 `git credential fill` 取到的 token
6. 本机开发：`cd backend && .venv\Scripts\python -m pytest -q`；前端 `cd frontend && npm run dev`
7. 踩过的坑：只重建 api 不重建 web 会整站 502（nginx 缓存上游 IP）；`docker compose run` 无 TTY 要加 `-T`；
   GitHub Actions 里步骤 skipped 不会让 job 变红（假绿）；PowerShell 5.1 传参吃引号，
   远端脚本要"上传 .sh 再执行"
