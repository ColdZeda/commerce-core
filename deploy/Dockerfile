# 两阶段：builder 里编译 mysqlclient 与 uWSGI，runtime 只带运行期库，避免把 gcc 带进镜像。
FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY backend/requirements.txt backend/requirements-prod.txt /wheels/
RUN pip wheel --wheel-dir /wheels -r /wheels/requirements.txt -r /wheels/requirements-prod.txt


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels -r /wheels/requirements.txt -r /wheels/requirements-prod.txt \
    && rm -rf /wheels

WORKDIR /app
COPY backend/ /app/
COPY deploy/uwsgi.ini /app/deploy/uwsgi.ini

RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uwsgi", "--ini", "/app/deploy/uwsgi.ini"]
