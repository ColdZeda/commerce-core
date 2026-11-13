#!/usr/bin/env bash
# 服务器侧部署脚本：由 CI 上传到 /opt/commerce-core/deploy.sh，再由 CI 通过 ssh 调用。
# 用法：./deploy.sh <image-tag>
#
# 只做两件危险事：改写 .env 的 IMAGE_TAG、重建容器。其余都是预检与验证。
# 失败时先回滚到上一版并确认站点恢复，再以非零退出——CI 只会看到一个红色结果加一段说明。

set -euo pipefail

TAG="${1:-}"
if [ -z "$TAG" ]; then
    echo "用法: $0 <image-tag>" >&2
    exit 64
fi

cd "$(dirname "$0")"

COMPOSE=(docker compose -f docker-compose.yml)
ENV_FILE=.env
CURRENT_FILE=.current_tag
PREVIOUS_FILE=.previous_tag
HEALTH_URL=http://127.0.0.1:8080/api/v1/health
ROOT_URL=http://127.0.0.1:8080/

# 记录已经走到哪一步：回滚时的动作取决于新镜像有没有被拉起来过
STAGE=preflight

log() { printf '[deploy %s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { log "失败：$*"; exit 1; }

read_env() {
    grep -E "^$1=" "$ENV_FILE" | head -n1 | cut -d= -f2-
}

set_env_tag() {
    if grep -qE '^IMAGE_TAG=' "$ENV_FILE"; then
        sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=$1|" "$ENV_FILE"
    else
        printf 'IMAGE_TAG=%s\n' "$1" >>"$ENV_FILE"
    fi
}

[ -f "$ENV_FILE" ] || die "$PWD 下没有 .env"

REGISTRY=$(read_env ACR_REGISTRY)
[ -n "$REGISTRY" ] || die ".env 缺少 ACR_REGISTRY"
API_IMAGE="$REGISTRY/commerce-core/api"
WEB_IMAGE="$REGISTRY/commerce-core/web"

OLD_TAG=$(read_env IMAGE_TAG)
[ -n "$OLD_TAG" ] || die ".env 缺少 IMAGE_TAG"

# 两个镜像必须都在：只有 api 换了 tag 而 web 没有时，nginx 会去连不存在的上游
images_exist() {
    docker manifest inspect "$API_IMAGE:$1" >/dev/null 2>&1 &&
        docker manifest inspect "$WEB_IMAGE:$1" >/dev/null 2>&1
}

# 60 秒内等健康接口与首页同时可用；容器 start_period 是 20 秒，uWSGI 起来还要几秒
wait_healthy() {
    local i
    for i in $(seq 1 30); do
        if curl -fsS -m 3 "$HEALTH_URL" >/dev/null 2>&1 &&
            [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' "$ROOT_URL")" = "200" ]; then
            return 0
        fi
        sleep 2
    done
    return 1
}

rollback() {
    local reason=$1
    log "开始回滚：$reason"

    # 新栈还没起来过：正在跑的仍是旧容器，改回 .env 即可，不需要动容器
    if [ "$STAGE" != "up" ] && [ "$STAGE" != "verify" ]; then
        set_env_tag "$OLD_TAG"
        if wait_healthy; then
            log "未起新栈，已把 IMAGE_TAG 改回 $OLD_TAG，现有栈健康"
        else
            log "未起新栈，已把 IMAGE_TAG 改回 $OLD_TAG，但现有栈健康检查未通过，需要人工查看"
        fi
        return 1
    fi

    if ! images_exist "$OLD_TAG"; then
        log "无法自动回滚：ACR 里没有 $OLD_TAG 的 api+web 完整镜像组"
        log "（首次从 S2 升级时会遇到这种情况，因为历史版本没有 web 镜像）"
        log "栈当前状态见 docker compose ps；不要在这里继续操作，交给人工决定"
        return 2
    fi

    set_env_tag "$OLD_TAG"
    "${COMPOSE[@]}" pull || log "回滚拉取镜像失败，继续尝试用本地已有镜像"
    "${COMPOSE[@]}" up -d --remove-orphans
    if wait_healthy; then
        log "已回滚到 $OLD_TAG，站点恢复"
        return 0
    fi
    log "回滚后仍不健康，需要人工介入"
    return 2
}

main() {
    log "目标 tag=$TAG，当前 tag=$OLD_TAG"

    STAGE=preflight
    images_exist "$TAG" || die "ACR 里找不到 $TAG 的 api+web 镜像，先确认 CI 的 build & push 是否成功"

    for key in ENABLE_MOCK_PAY PAY_CALLBACK_SECRET; do
        if [ -z "$(read_env "$key")" ]; then
            log "提醒：.env 里 $key 为空，相关功能（模拟支付/回调签名）会不可用"
        fi
    done

    # compose 的镜像 tag 来自 .env，所以先改 .env 再 pull，否则拉的是旧 tag。
    # 这一步之后任何失败都要把 .env 改回去，否则下次 up -d 会拿着不存在的镜像起栈。
    STAGE=prepare
    set_env_tag "$TAG"

    STAGE=pull
    log "拉取镜像 $TAG"
    if ! "${COMPOSE[@]}" pull; then
        rollback "拉取镜像失败" || true
        die "部署 $TAG 失败：拉取镜像"
    fi

    # 迁移必须先于起栈：旧代码在新库上仍要能跑（加法迁移纪律）
    STAGE=migrate
    log "执行迁移"
    if ! "${COMPOSE[@]}" run --rm -T api python manage.py migrate; then
        rollback "迁移失败" || true
        die "部署 $TAG 失败：迁移"
    fi

    STAGE=up
    log "重建容器"
    # --remove-orphans：S2 的 commerce-nginx 服务名已不存在，不清理会继续占着 8080
    if ! "${COMPOSE[@]}" up -d --remove-orphans; then
        rollback "重建容器失败" || true
        die "部署 $TAG 失败：重建容器"
    fi

    STAGE=verify
    log "等待健康检查"
    if ! wait_healthy; then
        "${COMPOSE[@]}" ps || true
        "${COMPOSE[@]}" logs --tail=40 api web || true
        rollback "健康检查未通过" || true
        die "部署 $TAG 失败：健康检查"
    fi

    echo "$OLD_TAG" >"$PREVIOUS_FILE"
    echo "$TAG" >"$CURRENT_FILE"
    log "部署完成：$TAG（上一版 $OLD_TAG 已记录到 $PREVIOUS_FILE）"
    "${COMPOSE[@]}" ps
}

main "$@"
