# syntax=docker/dockerfile:1
FROM ghcr.io/nvidia/openshell/gateway@sha256:05cf77bbb022a739aed6f22daa0e7e164415f4ab273b5f84319e46d91eb8f645 AS gateway
FROM debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 curl openssh-client rsync poppler-utils tini \
    && rm -rf /var/lib/apt/lists/*
COPY --from=gateway /usr/local/bin/openshell-gateway /usr/local/bin/openshell-gateway
COPY docker/runtime-lock.json docker/install_runtime.py /opt/bac/build/
ARG TARGETARCH
RUN python3 /opt/bac/build/install_runtime.py "$TARGETARCH"
ENV PATH="/opt/bac/runtime/node/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
COPY docker/runtime/package*.json /opt/bac/runtime/package/
RUN cd /opt/bac/runtime/package && npm ci --omit=dev --no-audit --no-fund && npm cache clean --force
RUN groupadd --gid 10001 bac && useradd --uid 10001 --gid bac --home-dir /var/lib/bac/home --no-create-home bac

COPY Dockerfile /opt/bac/source/Dockerfile
COPY docker/ /opt/bac/source/docker/
COPY docker/bootstrap.py /opt/bac/bootstrap.py
RUN python3 /opt/bac/bootstrap.py --stamp && rm -rf /opt/bac/source \
    && mkdir -p /opt/bac/app && chown 10001:10001 /opt/bac/app
ENV BAC_CONTAINER=1 BAC_DATA_DIR=/var/lib/bac \
    BAC_OPENCLAW_PORT=28689 BAC_OPENSHELL_PORT=28680 BAC_OPENSHELL_HEALTH_PORT=28681 \
    HOME=/var/lib/bac/home XDG_CONFIG_HOME=/var/lib/bac/home/.config \
    XDG_DATA_HOME=/var/lib/bac/home/.local/share OPENSHELL_GATEWAY=bac-demo \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/bac/app
USER 10001:10001
ENTRYPOINT ["/usr/bin/tini", "--", "python3", "/opt/bac/bootstrap.py"]
CMD ["serve"]

FROM runtime AS app
USER 0
LABEL org.opencontainers.image.title="BaC Agent Studio" \
      org.opencontainers.image.source="https://gitlab-master.nvidia.com/jinhol/bacdemo-tier2"
WORKDIR /opt/bac/app
COPY scripts/ scripts/
COPY src/ src/
COPY crew/ crew/
COPY skills/ skills/
COPY runtime/research-guard/ runtime/research-guard/
COPY docker/ docker/
COPY Dockerfile Dockerfile
COPY README.md ./

RUN mkdir -p app && python3 scripts/build.py
USER 10001:10001
ENTRYPOINT ["/usr/bin/tini", "--", "python3", "/opt/bac/app/scripts/container_runtime.py"]
CMD ["serve"]

FROM app AS test
COPY tests/ tests/
COPY bac launch.sh ./
COPY runtime/ runtime/
COPY compose.yaml compose.yaml
COPY docs/docker-setup.md docs/docker-setup.md
USER 0
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN env -u BAC_CONTAINER -u BAC_OPENCLAW_PORT python3 -B -m unittest discover -s tests -p 'test_*.py'

FROM runtime AS release
LABEL org.opencontainers.image.title="BaC Agent Studio" \
      org.opencontainers.image.source="https://gitlab-master.nvidia.com/jinhol/bacdemo-tier2"
