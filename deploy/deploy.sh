#!/usr/bin/env bash
# 服务器侧部署脚本：由 CI 上传到 /opt/commerce-core/deploy.sh，再由 CI 通过 ssh 调用。
# 用法：./deploy.sh <image-tag>
#
# 只做两件危险事：改写 .env 的 IMAGE_TAG、重建容器。其余都是预检与验证。
# 失败时先回滚到上一版并确认站点恢复，再以非零退出。
#
# 日志一律用 ASCII：GitHub Actions 的日志在非 UTF-8 locale 下会把中文显示成乱码，
# 出故障时正需要看清这些行。

set -euo pipefail

TAG="${1:-}"
if [ -z "$TAG" ]; then
    echo "usage: $0 <image-tag>" >&2
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
die() { log "FAILED: $*"; exit 1; }

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

[ -f "$ENV_FILE" ] || die "no $ENV_FILE in $PWD"

REGISTRY=$(read_env ACR_REGISTRY)
[ -n "$REGISTRY" ] || die "ACR_REGISTRY missing in $ENV_FILE"
API_IMAGE="$REGISTRY/commerce-core/api"
WEB_IMAGE="$REGISTRY/commerce-core/web"

OLD_TAG=$(read_env IMAGE_TAG)
[ -n "$OLD_TAG" ] || die "IMAGE_TAG missing in $ENV_FILE"

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
    log "rollback start: $reason"

    # 新栈还没起来过：正在跑的仍是旧容器，改回 .env 即可，不需要动容器
    if [ "$STAGE" != "up" ] && [ "$STAGE" != "verify" ]; then
        set_env_tag "$OLD_TAG"
        if wait_healthy; then
            log "no new stack was started; IMAGE_TAG restored to $OLD_TAG, running stack is healthy"
        else
            log "no new stack was started; IMAGE_TAG restored to $OLD_TAG but running stack health check FAILED"
        fi
        return 1
    fi

    if ! images_exist "$OLD_TAG"; then
        log "cannot rollback automatically: $OLD_TAG has no complete api+web image pair in ACR"
        log "(expected when upgrading from S2 - older tags were published before the web image existed)"
        log "current stack state: docker compose ps - stopping here for a manual decision"
        return 2
    fi

    set_env_tag "$OLD_TAG"
    "${COMPOSE[@]}" pull || log "rollback pull failed, trying local images"
    "${COMPOSE[@]}" up -d --remove-orphans
    if wait_healthy; then
        log "rolled back to $OLD_TAG, site is healthy again"
        return 0
    fi
    log "rollback finished but health still failing, manual intervention needed"
    return 2
}

main() {
    log "target=$TAG current=$OLD_TAG"

    STAGE=preflight
    images_exist "$TAG" || die "image $TAG not found in ACR (api+web), check build & push of this sha"

    for key in ENABLE_MOCK_PAY PAY_CALLBACK_SECRET; do
        if [ -z "$(read_env "$key")" ]; then
            log "warn: $key is empty in .env, related feature will not work"
        fi
    done

    # compose 的镜像 tag 来自 .env，所以先改 .env 再 pull，否则拉的是旧 tag。
    # 这一步之后任何失败都要把 .env 改回去，否则下次 up -d 会拿着不存在的镜像起栈。
    STAGE=prepare
    set_env_tag "$TAG"

    STAGE=pull
    log "pull images $TAG"
    if ! "${COMPOSE[@]}" pull; then
        rollback "pull failed" || true
        die "deploy $TAG aborted at pull"
    fi

    # 迁移必须先于起栈：旧代码在新库上仍要能跑（加法迁移纪律）
    STAGE=migrate
    log "run migrations"
    if ! "${COMPOSE[@]}" run --rm -T api python manage.py migrate; then
        rollback "migrate failed" || true
        die "deploy $TAG aborted at migrate"
    fi

    STAGE=up
    log "recreate containers"
    # --remove-orphans：S2 的 commerce-nginx 服务名已不存在，不清理会继续占着 8080
    if ! "${COMPOSE[@]}" up -d --remove-orphans; then
        rollback "up failed" || true
        die "deploy $TAG aborted at up"
    fi

    STAGE=verify
    log "wait for health"
    if ! wait_healthy; then
        "${COMPOSE[@]}" ps || true
        "${COMPOSE[@]}" logs --tail=40 api web || true
        rollback "health check failed" || true
        die "deploy $TAG aborted at health check"
    fi

    echo "$OLD_TAG" >"$PREVIOUS_FILE"
    echo "$TAG" >"$CURRENT_FILE"
    log "deployed $TAG (previous=$OLD_TAG recorded in $PREVIOUS_FILE)"
    "${COMPOSE[@]}" ps
}

main "$@"
