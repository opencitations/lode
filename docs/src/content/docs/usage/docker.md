---
title: Docker
description: Deploy LODE with Docker
---

## Quick start

```bash
docker build -t lode .
docker run -p 8000:8000 lode
```

Open `http://localhost:8000`.

## With persistent storage

```bash
docker run -p 8000:8000 \
  -v lode-data:/data \
  -e LODE_SPOOL_DIR=/data/spool \
  -e LODE_BUILD_DIR=/data/builds \
  lode
```

## Production (read-only filesystem)

```bash
docker run -p 8000:8000 \
  --read-only \
  --tmpfs /tmp \
  -v lode-data:/data \
  -e LODE_SPOOL_DIR=/data/spool \
  -e LODE_BUILD_DIR=/data/builds \
  lode
```

## From the registry

Once published:

```bash
docker run -p 8000:8000 ghcr.io/opencitations/lode:latest
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LODE_SPOOL_DIR` | `/tmp/lode-spool` | Cache directory |
| `LODE_BUILD_DIR` | `/tmp/lode-builds` | Build workspace |
| `LODE_DEBUG` | `false` | Enable debug tracebacks |
