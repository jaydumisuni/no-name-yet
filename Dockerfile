FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/sergeant

COPY pyproject.toml README.md ./
COPY main_review ./main_review
COPY resources ./resources
COPY review-benchmarks ./review-benchmarks

RUN python -m pip install --no-cache-dir . \
    && groupadd --system sergeant \
    && useradd --system --gid sergeant --home-dir /nonexistent --shell /usr/sbin/nologin sergeant \
    && mkdir -p /workspace \
    && chown sergeant:sergeant /workspace

USER sergeant
WORKDIR /workspace

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import json,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3)); assert data['status']=='ready'"

ENTRYPOINT ["sergeant-serve"]
CMD ["--workspace", "/workspace", "--host", "0.0.0.0", "--port", "8765"]
