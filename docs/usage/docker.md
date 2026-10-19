# Docker

The image listens on port `8080`.

## Quick start

```bash
docker build -t lode .
docker run -p 8080:8080 lode
```

Open `http://localhost:8080`.

## From Docker Hub

```bash
docker run -p 8080:8080 opencitations/lode:latest
```

Replace `latest` with the desired version tag.

## With persistent storage

```bash
docker run -p 8080:8080 \
  -v lode-data:/data \
  -e LODE_SPOOL_DIR=/data/spool \
  -e LODE_BUILD_DIR=/data/builds \
  opencitations/lode:latest
```

## Production (read-only filesystem)

```bash
docker run -p 8080:8080 \
  --read-only \
  --tmpfs /tmp \
  -v lode-data:/data \
  -e LODE_SPOOL_DIR=/data/spool \
  -e LODE_BUILD_DIR=/data/builds \
  opencitations/lode:latest
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LODE_SPOOL_DIR` | `/tmp/lode-spool` | Cache directory |
| `LODE_BUILD_DIR` | `/tmp/lode-builds` | Build workspace |
| `LODE_DEBUG` | `false` | Enable debug tracebacks |
