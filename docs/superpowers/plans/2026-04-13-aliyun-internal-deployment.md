# Aliyun + 内网混合部署 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy AI Webtoon Studio to Aliyun Beijing (public entry) with ComfyUI on a NAT-bound home GPU machine, connected via FRP reverse tunnel. Ship in two phases: Phase 1 (IP + non-standard port, usable during ICP filing), Phase 2 (domain + TLS after filing completes).

**Architecture:** Aliyun runs Nginx + Next.js + FastAPI + Celery worker + Postgres + Redis + MinIO + frps in Docker Compose. Internal GPU machine runs ComfyUI (loopback-only) + frpc which dials out to frps and exposes ComfyUI on Aliyun's `127.0.0.1:18188`. Celery worker talks to `http://host.docker.internal:18188` like it's local.

**Tech Stack:** Docker Compose, Nginx, FRP (fatedier/frp), Let's Encrypt (certbot), existing app stack (FastAPI, Next.js, Celery, Postgres, Redis, MinIO).

**Spec:** `docs/superpowers/specs/2026-04-13-aliyun-internal-deployment-design.md`

---

## Phase A — Repository artifacts (committable, done locally)

All of Phase A is done in the current working repo. Tasks A1–A5 produce config files that get checked in. Phase B onward runs on the actual servers.

---

### Task A1: Production Docker Compose file

**Files:**
- Create: `docker/docker-compose.prod.yml`

This sits alongside the existing dev `docker-compose.yml` but differs in:
- Restart policies everywhere
- Host-path volumes (not named volumes) for data persistence
- Data-layer services bind to loopback on host (not public)
- App services don't publish ports directly (Nginx is the only public face in Phase 2; in Phase 1 Nginx publishes 8000)
- Worker reads `COMFYUI_URL` from `.env.prod`
- frps service runs in host network mode so its reverse-proxy port can bind to host loopback
- Celery entrypoint fixed to `app.celery_app:celery_app` (existing dev compose uses wrong `app.tasks`)

- [ ] **Step 1: Create `docker/docker-compose.prod.yml`**

```yaml
services:
  postgres:
    image: postgres:15-alpine
    container_name: webtoon-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - /srv/webtoon/data/postgres:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: webtoon-redis
    restart: unless-stopped
    volumes:
      - /srv/webtoon/data/redis:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    container_name: webtoon-minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - /srv/webtoon/data/minio:/data
    ports:
      - "127.0.0.1:9000:9000"
      - "127.0.0.1:9001:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile.api
    container_name: webtoon-api
    restart: unless-stopped
    env_file:
      - .env.prod
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ../apps/api:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build:
      context: ..
      dockerfile: docker/Dockerfile.api
    container_name: webtoon-worker
    restart: unless-stopped
    env_file:
      - .env.prod
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      COMFYUI_URL: http://host.docker.internal:18188
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      api:
        condition: service_started
      redis:
        condition: service_healthy
    volumes:
      - ../apps/api:/app
    command: celery -A app.celery_app:celery_app worker --loglevel=info -Q image,anchor,video,export,default

  web:
    build:
      context: ..
      dockerfile: docker/Dockerfile.web
    container_name: webtoon-web
    restart: unless-stopped
    env_file:
      - .env.prod
    depends_on:
      - api
    volumes:
      - ../apps/web:/app
      - /app/node_modules
      - /app/.next
    command: npm run dev

  nginx:
    image: nginx:1.27-alpine
    container_name: webtoon-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "8000:8000"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - /srv/webtoon/config/certbot/conf:/etc/letsencrypt:ro
      - /srv/webtoon/config/certbot/www:/var/www/certbot:ro
    depends_on:
      - api
      - web
      - minio

  frps:
    image: snowdreamtech/frps:0.58.1
    container_name: webtoon-frps
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./frp/frps.toml:/etc/frp/frps.toml:ro
    command: ["-c", "/etc/frp/frps.toml"]
```

- [ ] **Step 2: Verify YAML parses**

Run: `cd docker && docker compose -f docker-compose.prod.yml config --quiet`
Expected: no output (valid) — or, if `.env.prod` isn't written yet, errors only about missing variables (that's fine; config syntax is OK).

- [ ] **Step 3: Commit**

```bash
git add docker/docker-compose.prod.yml
git commit -m "feat(deploy): add production docker-compose for Aliyun"
```

---

### Task A2: Nginx config for Phase 1 (IP + port 8000)

**Files:**
- Create: `docker/nginx/conf.d/phase1-ip.conf`

Phase 1 server block: listens on 8000 (since 80/443 on unfiled domains are blocked by Aliyun platform checks in mainland), serves the 3 upstreams + MinIO `/media` path.

- [ ] **Step 1: Create the Phase 1 server block**

```nginx
# Phase 1: IP + port 8000, HTTP only. Used during ICP filing.
# Swap to phase2-domain.conf once filing completes.

upstream webtoon_api  { server api:8000; }
upstream webtoon_web  { server web:3001; }
upstream webtoon_minio { server minio:9000; }

server {
    listen 8000;
    server_name _;

    client_max_body_size 100M;

    # API
    location /api/ {
        proxy_pass         http://webtoon_api;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_read_timeout 300s;
    }

    # WebSocket
    location /ws {
        proxy_pass         http://webtoon_api;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host       $host;
        proxy_read_timeout 3600s;
    }

    # MinIO presigned URLs
    location /media/ {
        proxy_pass         http://webtoon_minio/;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
    }

    # Next.js (catch-all)
    location / {
        proxy_pass         http://webtoon_web;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;

        # Next.js HMR websocket (dev mode)
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
    }
}
```

- [ ] **Step 2: Verify config syntax**

Run (from repo root):
```bash
docker run --rm -v "$(pwd)/docker/nginx/conf.d:/etc/nginx/conf.d:ro" nginx:1.27-alpine nginx -t
```
Expected: `nginx: the configuration file /etc/nginx/nginx.conf syntax is ok` (may warn about missing upstreams — that's OK in standalone test).

- [ ] **Step 3: Commit**

```bash
git add docker/nginx/conf.d/phase1-ip.conf
git commit -m "feat(deploy): add phase 1 nginx config (IP + port 8000)"
```

---

### Task A3: Nginx config template for Phase 2 (domain + TLS)

**Files:**
- Create: `docker/nginx/conf.d/phase2-domain.conf.example`

Phase 2 template — do NOT drop this file into `conf.d/` until DNS is pointed and certbot has run. Filename ends in `.example` so Nginx won't load it until the engineer copies/renames it.

- [ ] **Step 1: Create the Phase 2 template**

```nginx
# Phase 2: domain + HTTPS. Rename to *.conf after ICP filing + certbot.
# Replace YOUR_DOMAIN with your registered+filed domain.

upstream webtoon_api  { server api:8000; }
upstream webtoon_web  { server web:3001; }
upstream webtoon_minio { server minio:9000; }

# HTTP → HTTPS redirect + ACME challenge
server {
    listen 80;
    server_name YOUR_DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name YOUR_DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_cache   shared:SSL:10m;

    client_max_body_size 100M;

    location /api/ {
        proxy_pass         http://webtoon_api;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_read_timeout 300s;
    }

    location /ws {
        proxy_pass         http://webtoon_api;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host       $host;
        proxy_read_timeout 3600s;
    }

    location /media/ {
        proxy_pass         http://webtoon_minio/;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
    }

    location / {
        proxy_pass         http://webtoon_web;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add docker/nginx/conf.d/phase2-domain.conf.example
git commit -m "feat(deploy): add phase 2 nginx template (domain + TLS)"
```

---

### Task A4: FRP configuration files

**Files:**
- Create: `docker/frp/frps.toml`
- Create: `docker/frp/frpc.toml.example`

frps config is committed (no secrets in it — token comes from env substitution at deploy time via a wrapper script, OR we generate a gitignored `frps.toml` from a template; simplest is to keep the token in a sibling file that's gitignored).

Chosen approach: commit `frps.toml` with a placeholder token `<FRP_TOKEN_FILL_ME>`, and require the deployer to replace it at install time. Also write `frpc.toml.example` as a template for the internal machine.

- [ ] **Step 1: Create `docker/frp/frps.toml`**

```toml
# Aliyun-side FRP server
bindAddr  = "0.0.0.0"
bindPort  = 7000

auth.method = "token"
auth.token  = "<FRP_TOKEN_FILL_ME>"

transport.tls.force = true

# Only allow clients to open port 18188 for reverse proxying
allowPorts = [
  { start = 18188, end = 18188 },
]

# Dashboard (loopback only, SSH-tunnel to view)
webServer.addr = "127.0.0.1"
webServer.port = 7500
webServer.user = "admin"
webServer.password = "<FRP_DASHBOARD_PASSWORD_FILL_ME>"
```

- [ ] **Step 2: Create `docker/frp/frpc.toml.example`**

```toml
# Internal-machine FRP client. Copy to /etc/frp/frpc.toml and fill in values.

serverAddr = "<ALIYUN_PUBLIC_IP>"
serverPort = 7000

auth.method = "token"
auth.token  = "<SAME_TOKEN_AS_FRPS>"

transport.tls.enable = true

[[proxies]]
name      = "comfyui"
type      = "tcp"
localIP   = "127.0.0.1"
localPort = 8188
remotePort = 18188
```

- [ ] **Step 3: Commit**

```bash
git add docker/frp/frps.toml docker/frp/frpc.toml.example
git commit -m "feat(deploy): add FRP server+client config templates"
```

---

### Task A5: Production env template

**Files:**
- Create: `docker/.env.prod.example`
- Modify: `.gitignore` (ensure `config/.env.prod` never lands in git)

- [ ] **Step 1: Create `docker/.env.prod.example`**

```dotenv
# On the Aliyun server: copy to docker/.env.prod (alongside docker-compose.prod.yml) and fill real values.
# This file is gitignored. Never commit the filled-in version.

# ---- Postgres ----
POSTGRES_USER=webtoon
POSTGRES_PASSWORD=<GENERATE: openssl rand -base64 24>
POSTGRES_DB=webtoon_studio

# ---- MinIO ----
MINIO_ROOT_USER=webtoon
MINIO_ROOT_PASSWORD=<GENERATE: openssl rand -base64 24>
MINIO_ACCESS_KEY=webtoon
MINIO_SECRET_KEY=<SAME AS MINIO_ROOT_PASSWORD>
MINIO_BUCKET=webtoon-assets
MINIO_SECURE=false

# ---- App ----
APP_NAME=AI Webtoon Studio
DEBUG=false
LOG_LEVEL=INFO

# ---- Auth ----
ENABLE_AUTH=true
JWT_SECRET=<GENERATE: openssl rand -base64 48>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=<GENERATE>
INITIAL_ADMIN_EMAIL=admin@example.com

# ---- CORS (Phase 1: use http://<aliyun-ip>:8000; Phase 2: https://yourdomain.com) ----
CORS_ORIGINS=["http://<ALIYUN_IP>:8000"]

# ---- LLM provider ----
LLM_PROVIDER=doubao
LLM_MODEL=doubao-pro-32k
DOUBAO_API_KEY=<FROM VOLCENGINE ARK CONSOLE>
ARK_API_KEY=<FROM VOLCENGINE ARK CONSOLE>
DOUBAO_IMAGE_MODEL=doubao-seedream-4.5

# ---- Optional backup LLM ----
# TONGYI_API_KEY=
# OPENAI_API_KEY=
# DEEPSEEK_API_KEY=

# ---- ComfyUI (reached via FRP tunnel) ----
# worker uses host.docker.internal:18188 (set in compose), not via .env
# Leave COMFYUI_URL unset here so compose's env wins.

# ---- Next.js public env (Phase 1) ----
NEXT_PUBLIC_API_BASE_URL=http://<ALIYUN_IP>:8000
NEXT_PUBLIC_WS_BASE_URL=ws://<ALIYUN_IP>:8000
NEXT_PUBLIC_USE_REAL_WS=true

# ---- Database init strategy ----
DB_AUTO_CREATE=false
DB_RUN_LIGHT_MIGRATIONS=false
```

- [ ] **Step 2: Update `.gitignore`**

Append to the existing `.gitignore`:

```
# Production secrets — never commit
docker/.env.prod
docker/frp/frpc.toml
```

- [ ] **Step 3: Verify `.gitignore` is applied**

Run: `git check-ignore -v docker/.env.prod docker/frp/frpc.toml` (files don't need to exist; `-v` shows the rule).
Expected: both paths print a `.gitignore` rule line.

- [ ] **Step 4: Commit**

```bash
git add docker/.env.prod.example .gitignore
git commit -m "feat(deploy): add .env.prod template and ignore secrets"
```

---

### Task A6: Operations runbook

**Files:**
- Create: `docs/deployment/README.md`

Single doc the on-call engineer reads first. Covers: what goes where, how to start/stop, how to check logs, how to rotate a token, how to do Phase 2 switchover.

- [ ] **Step 1: Create `docs/deployment/README.md`**

```markdown
# Deployment Runbook

Production deployment of AI Webtoon Studio. Spec: `docs/superpowers/specs/2026-04-13-aliyun-internal-deployment-design.md`.

## Topology
- **Aliyun Beijing ECS** (public): Nginx, Next.js, FastAPI, Celery, Postgres, Redis, MinIO, frps
- **Home GPU machine** (NAT): ComfyUI + frpc (dial-out only)
- Connection: FRP reverse tunnel, ComfyUI exposed on Aliyun's `127.0.0.1:18188`

## Aliyun layout
```
/srv/webtoon/
├── source/              # git repo
│   └── docker/
│       ├── docker-compose.prod.yml
│       ├── .env.prod    # secrets, gitignored
│       ├── nginx/conf.d/
│       └── frp/frps.toml
├── data/                # persistent volumes (postgres/redis/minio)
├── config/
│   └── certbot/         # Let's Encrypt state (Phase 2)
└── logs/
```

## Common commands

All run from `/srv/webtoon/source/docker`:

```bash
cd /srv/webtoon/source/docker

# Start everything
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Stop everything
docker compose -f docker-compose.prod.yml --env-file .env.prod down

# Tail logs for one service
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f worker

# Restart after a code change
docker compose -f docker-compose.prod.yml restart api worker

# Run DB migration
docker compose -f docker-compose.prod.yml --env-file .env.prod exec api alembic upgrade head
```

## Secrets checklist (done once at install)

On Aliyun:
1. `docker/.env.prod` — copy from `docker/.env.prod.example`, fill secrets (gitignored; stays local on server)
2. `docker/frp/frps.toml` — replace `<FRP_TOKEN_FILL_ME>` and `<FRP_DASHBOARD_PASSWORD_FILL_ME>` (file is tracked in git; DO NOT commit the filled version — edit in place on the server and use `git update-index --skip-worktree docker/frp/frps.toml` to prevent accidental commits)

On internal GPU machine:
3. `/etc/frp/frpc.toml` — copy from `docker/frp/frpc.toml.example`, fill `serverAddr` + `token`

## FRP tunnel health check

```bash
# From Aliyun: test reverse tunnel
curl http://127.0.0.1:18188/system_stats
# Expected: JSON with ComfyUI system info

# FRP dashboard (SSH tunnel from laptop)
ssh -L 7500:127.0.0.1:7500 <aliyun-user>@<aliyun-ip>
# Then open http://localhost:7500 in browser (credentials from frps.toml)
```

## Phase 2 switchover (after ICP filing completes)

1. Point domain A record to Aliyun IP; wait for DNS propagation
2. Get initial cert:
   ```bash
   docker run --rm -v /srv/webtoon/config/certbot/conf:/etc/letsencrypt \
     -v /srv/webtoon/config/certbot/www:/var/www/certbot \
     -p 80:80 certbot/certbot certonly --standalone -d yourdomain.com \
     --email you@example.com --agree-tos --non-interactive
   ```
   (Stop Nginx first so certbot can bind 80.)
3. Copy the phase 2 template and fill domain:
   ```bash
   cd /srv/webtoon/source/docker/nginx/conf.d
   cp phase2-domain.conf.example phase2-domain.conf
   sed -i 's/YOUR_DOMAIN/yourdomain.com/g' phase2-domain.conf
   rm phase1-ip.conf
   ```
4. Update `.env.prod`:
   - `CORS_ORIGINS=["https://yourdomain.com"]`
   - `NEXT_PUBLIC_API_BASE_URL=https://yourdomain.com`
   - `NEXT_PUBLIC_WS_BASE_URL=wss://yourdomain.com`
5. Rebuild web + restart Nginx:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate web nginx
   ```
6. Close port 8000 on Aliyun security group; keep 80 + 443 open.

## Cert renewal (Phase 2)

Add to crontab:
```
0 3 * * * docker run --rm -v /srv/webtoon/config/certbot/conf:/etc/letsencrypt -v /srv/webtoon/config/certbot/www:/var/www/certbot certbot/certbot renew --quiet && docker exec webtoon-nginx nginx -s reload
```

## Rotating the FRP token

1. On Aliyun: edit `docker/frp/frps.toml`, change `auth.token`, `docker compose -f docker-compose.prod.yml restart frps`
2. On internal machine: edit `/etc/frp/frpc.toml`, change `auth.token`, `systemctl restart frpc`

## Backup hooks (to be added later)

Not covered in Phase 1. Track in next spec:
- Postgres: `pg_dump` to OSS nightly
- MinIO: `mc mirror` to OSS nightly
```

- [ ] **Step 2: Commit**

```bash
git add docs/deployment/README.md
git commit -m "docs(deploy): add operations runbook"
```

---

## Phase B — Aliyun server bootstrap

Operational steps run on the Aliyun VM. Each task below assumes you are SSH'd into the server as a user with sudo.

---

### Task B1: Provision Aliyun ECS + firewall + Docker

- [ ] **Step 1: Buy a Beijing ECS**

In Aliyun console:
- Region: 华北2（北京）
- Type: general-purpose 2 vCPU / 4 GB RAM (e.g. `ecs.u1-c1m2.large`)
- OS: Ubuntu 22.04 LTS
- System disk: 40 GB ESSD
- Data disk: 100 GB ESSD (mounted at `/srv`)
- Public IP: bind an **Elastic IP** (so it won't change)
- Security group — initial ruleset:
  - Inbound: 22 from your home IP only
  - Inbound: 8000 from anywhere (Phase 1 temporary)
  - Inbound: 7000 from your home IP only (FRP control; if home IP changes, broaden to `0.0.0.0/0` and rely on token+TLS)
  - Outbound: all

- [ ] **Step 2: Format and mount the data disk**

```bash
# Check disk name (likely /dev/vdb)
lsblk
sudo mkfs.ext4 /dev/vdb
sudo mkdir -p /srv
sudo mount /dev/vdb /srv
echo "/dev/vdb /srv ext4 defaults,noatime 0 2" | sudo tee -a /etc/fstab
```

Verify: `df -h /srv` shows the 100 GB disk mounted.

- [ ] **Step 3: Install Docker + Compose**

```bash
sudo apt update && sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

Verify: `docker run --rm hello-world` prints the hello message.

- [ ] **Step 4: Check platform network**

Run: `curl -sI https://ark.cn-beijing.volces.com` and `curl -sI https://dashscope.aliyuncs.com`
Expected: `HTTP/2 200` or redirect — confirms outbound to the LLM APIs works.

No commit (operational).

---

### Task B2: Directory layout, clone repo, write secrets

- [ ] **Step 1: Create directory tree**

```bash
sudo mkdir -p /srv/webtoon/{source,data/postgres,data/redis,data/minio,config,logs}
sudo chown -R $USER:$USER /srv/webtoon
```

- [ ] **Step 2: Clone the repo**

```bash
cd /srv/webtoon
git clone <your-git-remote-url> source
cd source
git checkout main   # or the production branch you decide on
```

- [ ] **Step 3: Generate secrets and write `.env.prod`**

```bash
cd /srv/webtoon/source/docker
cp .env.prod.example .env.prod
chmod 600 .env.prod

# Generate strong values
PG_PW=$(openssl rand -base64 24)
MINIO_PW=$(openssl rand -base64 24)
JWT=$(openssl rand -base64 48)
ADMIN_PW=$(openssl rand -base64 16)
ALIYUN_IP=$(curl -s https://ifconfig.me)

echo "Postgres password: $PG_PW"
echo "MinIO password:    $MINIO_PW"
echo "JWT secret:        $JWT"
echo "Admin password:    $ADMIN_PW"
echo "Aliyun IP:         $ALIYUN_IP"
```

Then edit `docker/.env.prod` with your editor and paste the values. Also fill `DOUBAO_API_KEY` / `ARK_API_KEY` from your Volcengine console, and replace `<ALIYUN_IP>` in `CORS_ORIGINS` / `NEXT_PUBLIC_*`.

- [ ] **Step 4: Write the FRP token**

```bash
FRP_TOKEN=$(openssl rand -base64 32)
FRP_DASH_PW=$(openssl rand -base64 16)
echo "FRP token:          $FRP_TOKEN"
echo "FRP dashboard pw:   $FRP_DASH_PW"
# Save these — you'll also put FRP_TOKEN on the internal machine

cd /srv/webtoon/source/docker/frp
sed -i "s|<FRP_TOKEN_FILL_ME>|$FRP_TOKEN|" frps.toml
sed -i "s|<FRP_DASHBOARD_PASSWORD_FILL_ME>|$FRP_DASH_PW|" frps.toml
```

Note: `frps.toml` is a tracked file. The edits above are local-only and must NOT be pushed. If you use git on the server, `git update-index --skip-worktree docker/frp/frps.toml` to prevent accidental commits.

- [ ] **Step 5: Verify**

```bash
# Check no plaintext placeholders remain
grep FILL_ME /srv/webtoon/source/docker/frp/frps.toml /srv/webtoon/source/docker/.env.prod
grep '<ALIYUN_IP>' /srv/webtoon/source/docker/.env.prod
# Expected: no output from either command
```

No commit.

---

### Task B3: Bring up data layer + run migrations

- [ ] **Step 1: Start data services**

```bash
cd /srv/webtoon/source/docker
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d postgres redis minio
```

- [ ] **Step 2: Wait for healthy**

```bash
docker compose -f docker-compose.prod.yml ps
```
Expected: `postgres`, `redis`, `minio` all show `(healthy)` within ~30 s.

- [ ] **Step 3: Create MinIO bucket**

```bash
ENV=/srv/webtoon/source/docker/.env.prod
docker run --rm --network host \
  -e MC_HOST_local=http://$(grep '^MINIO_ROOT_USER=' $ENV | cut -d= -f2-):$(grep '^MINIO_ROOT_PASSWORD=' $ENV | cut -d= -f2-)@127.0.0.1:9000 \
  minio/mc mb --ignore-existing local/webtoon-assets
```
Expected: `Bucket created successfully` or `Bucket already exists`.

- [ ] **Step 4: Build the API image and run migrations**

```bash
cd /srv/webtoon/source/docker
docker compose -f docker-compose.prod.yml --env-file .env.prod build api
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm api alembic upgrade head
```
Expected: alembic prints migrations applied (or "already at head" if none pending).

- [ ] **Step 5: Verify tables exist**

```bash
cd /srv/webtoon/source/docker
docker compose -f docker-compose.prod.yml exec postgres psql -U $(grep '^POSTGRES_USER=' .env.prod | cut -d= -f2-) -d webtoon_studio -c '\dt' | head -30
```
Expected: lists `projects`, `chapters`, `panels`, `assets`, `users`, … tables.

No commit.

---

### Task B4: Bring up app layer + frps

- [ ] **Step 1: Start all remaining services**

```bash
cd /srv/webtoon/source/docker
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d api worker web nginx frps
```

- [ ] **Step 2: Verify each container is up**

```bash
docker compose -f docker-compose.prod.yml ps
```
Expected: all 8 containers `Up`. `web` may take 30–60s to finish `npm install` on first start — tail logs: `docker compose logs -f web`.

- [ ] **Step 3: Probe each service from the host**

```bash
# Nginx is the only public face
curl -s http://127.0.0.1:8000/api/health    # expects {"status":"ok"} or similar
curl -sI http://127.0.0.1:8000/             # expects 200 or 307 (Next.js)
# frps listening
ss -tlnp | grep 7000                        # expects 0.0.0.0:7000
# The reverse-proxied port is NOT bound yet (no frpc connected)
ss -tlnp | grep 18188                       # expects no output
```

- [ ] **Step 4: Probe from your laptop**

```bash
curl -s http://<ALIYUN_IP>:8000/api/health
```
Expected: same as from host. If it fails, the Aliyun security group for port 8000 is blocking — fix in console.

No commit.

---

## Phase C — Internal GPU machine bootstrap

Operational steps on your home GPU box. Assumes Linux (Ubuntu/Debian); if Windows, swap `systemctl` for Task Scheduler or use NSSM.

---

### Task C1: Configure ComfyUI to bind loopback only

- [ ] **Step 1: Ensure ComfyUI runs with `--listen 127.0.0.1 --port 8188`**

Wherever you currently start ComfyUI (manual command, shell script, systemd unit), the launch command must be:

```bash
python main.py --listen 127.0.0.1 --port 8188
```

Do NOT use `--listen 0.0.0.0` or `--listen 0.0.0.0/::` — that exposes ComfyUI to your LAN.

- [ ] **Step 2: Verify**

```bash
curl -s http://127.0.0.1:8188/system_stats
curl -s --connect-timeout 3 http://<lan-ip-of-gpu-box>:8188/system_stats
```
Expected: first call returns JSON, second call times out or refuses connection.

No commit.

---

### Task C2: Install frpc + systemd service

- [ ] **Step 1: Download frpc binary**

```bash
cd /tmp
wget https://github.com/fatedier/frp/releases/download/v0.58.1/frp_0.58.1_linux_amd64.tar.gz
tar xf frp_0.58.1_linux_amd64.tar.gz
sudo install -m 0755 frp_0.58.1_linux_amd64/frpc /usr/local/bin/frpc
frpc --version
```
Expected: `0.58.1`.

- [ ] **Step 2: Write `/etc/frp/frpc.toml`**

```bash
sudo mkdir -p /etc/frp
sudo cp /path/to/webtoon/source/docker/frp/frpc.toml.example /etc/frp/frpc.toml
# OR manually write it by pasting from the repo example
sudo chmod 600 /etc/frp/frpc.toml
sudo nano /etc/frp/frpc.toml
# Replace <ALIYUN_PUBLIC_IP> and <SAME_TOKEN_AS_FRPS> with values from Task B2 step 4
```

- [ ] **Step 3: Create systemd unit**

```bash
sudo tee /etc/systemd/system/frpc.service > /dev/null <<'EOF'
[Unit]
Description=frp client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/frpc -c /etc/frp/frpc.toml
Restart=always
RestartSec=10
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now frpc
```

- [ ] **Step 4: Verify frpc connected**

```bash
sudo journalctl -u frpc -f --no-pager
# Look for: "[I] [sub.go:...] [comfyui] proxy added: ..."  and  "login to server success"
# Ctrl+C to exit
```

- [ ] **Step 5: Verify from Aliyun**

SSH back to Aliyun:
```bash
ss -tlnp | grep 18188
# Expected: 0.0.0.0:18188 (or 127.0.0.1:18188 — either OK since we restricted with allowPorts)
curl -s http://127.0.0.1:18188/system_stats
# Expected: JSON with ComfyUI system info (the internal machine's GPU etc.)
```

No commit.

---

## Phase D — End-to-end verification

---

### Task D1: FRP tunnel health check from the worker container

- [ ] **Step 1: Exec into the worker container**

On Aliyun:
```bash
cd /srv/webtoon/source/docker
docker compose -f docker-compose.prod.yml exec worker \
  curl -s http://host.docker.internal:18188/system_stats
```
Expected: same JSON as Task C2 step 5 — confirms the full path (container → host gateway → frps → frp tunnel → frpc → ComfyUI).

If it fails:
- Check `extra_hosts` in compose (must be `host.docker.internal:host-gateway`)
- Try `curl http://172.17.0.1:18188/system_stats` (the default docker0 bridge IP) to confirm the tunnel is OK but the hostname resolution is wrong.

No commit.

---

### Task D2: Full pipeline smoke test

- [ ] **Step 1: Register a user via the web UI**

Open `http://<ALIYUN_IP>:8000` in a browser. Click register (or use the `admin` / `<ADMIN_PW>` from `.env.prod`).

- [ ] **Step 2: Create a project and a chapter**

Use the web UI.

- [ ] **Step 3: Submit a small LLM analysis + storyboard request**

Type a one-paragraph test script and run the Director Agent. Expected: within 10–30 s, storyboard draft appears.
Verify in logs:
```bash
docker compose -f docker-compose.prod.yml logs -f api | grep -i doubao
```
Expected: outbound calls to Doubao API succeed.

- [ ] **Step 4: Render a single panel**

Click "Render" on one panel. Expected sequence:
1. API creates a `RenderJob`
2. Celery worker picks it up (`docker compose logs -f worker`)
3. Worker POSTs to `http://host.docker.internal:18188/prompt`
4. Internal machine runs ComfyUI inference
5. Worker downloads artifacts, uploads to MinIO
6. WS event `layerpack_ready` fires; UI updates

Verify in MinIO:
```bash
docker run --rm --network host -e MC_HOST_local=... minio/mc ls local/webtoon-assets --recursive | tail
```
Expected: fresh PNGs under `panels/<panel_id>/...`.

- [ ] **Step 5: Render a short video clip**

Use video generation on one panel. This exercises a different queue (`video`). Expected similar end-to-end flow; MP4 lands in MinIO.

If all 5 steps pass, Phase 1 is production-ready.

No commit.

---

## Phase E — ICP filing + Phase 2 switchover (async, takes 2–4 weeks)

---

### Task E1: Start ICP filing

- [ ] **Step 1: Buy a domain through Aliyun**

Aliyun console → 域名 → choose a `.com` or `.cn`. Cost ~¥55/yr.

- [ ] **Step 2: Initiate ICP filing**

Aliyun console → 备案 → add website → bind to your Beijing ECS + your domain. Follow the wizard (ID photo, 幕布照片, 真实性核验单). Submit and wait.

- [ ] **Step 3: Continue operating on Phase 1 until filing completes**

No action until Aliyun sends the "备案通过" notification (usually email + SMS).

---

### Task E2: Phase 2 switchover (run only after Task E1 approves)

- [ ] **Step 1: DNS A record**

Aliyun DNS → add A record `yourdomain.com → <ALIYUN_IP>`. Wait for propagation (verify with `dig yourdomain.com` from your laptop).

- [ ] **Step 2: Temporarily stop Nginx to free port 80**

```bash
cd /srv/webtoon/source/docker
docker compose -f docker-compose.prod.yml stop nginx
```

- [ ] **Step 3: Get initial cert**

```bash
sudo mkdir -p /srv/webtoon/config/certbot/conf /srv/webtoon/config/certbot/www
docker run --rm \
  -v /srv/webtoon/config/certbot/conf:/etc/letsencrypt \
  -v /srv/webtoon/config/certbot/www:/var/www/certbot \
  -p 80:80 \
  certbot/certbot certonly --standalone \
  -d yourdomain.com \
  --email you@example.com --agree-tos --non-interactive
```
Expected: `Successfully received certificate. Certificate is saved at: /etc/letsencrypt/live/yourdomain.com/fullchain.pem`.

- [ ] **Step 4: Swap Nginx config**

```bash
cd /srv/webtoon/source/docker/nginx/conf.d
cp phase2-domain.conf.example phase2-domain.conf
sed -i 's/YOUR_DOMAIN/yourdomain.com/g' phase2-domain.conf
rm phase1-ip.conf
```

- [ ] **Step 5: Update `.env.prod` URLs**

Edit `/srv/webtoon/source/docker/.env.prod`:
```
CORS_ORIGINS=["https://yourdomain.com"]
NEXT_PUBLIC_API_BASE_URL=https://yourdomain.com
NEXT_PUBLIC_WS_BASE_URL=wss://yourdomain.com
```

- [ ] **Step 6: Restart web + nginx**

```bash
cd /srv/webtoon/source/docker
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate web nginx
```

- [ ] **Step 7: Close Phase 1 port**

Aliyun console → security group → remove the 8000 inbound rule. Keep 80 and 443.

- [ ] **Step 8: Verify**

From your laptop:
```bash
curl -sI https://yourdomain.com/         # expect 200 (Next.js)
curl -s  https://yourdomain.com/api/health   # expect {"status":"ok"} etc.
```
Open `https://yourdomain.com` in a browser — full pipeline should still work.

- [ ] **Step 9: Install cert auto-renewal cron**

On Aliyun host:
```bash
(crontab -l 2>/dev/null; echo "0 3 * * * docker run --rm -v /srv/webtoon/config/certbot/conf:/etc/letsencrypt -v /srv/webtoon/config/certbot/www:/var/www/certbot certbot/certbot renew --quiet && docker exec webtoon-nginx nginx -s reload") | crontab -
```

No commit (operational); Phase 2 is now live.

---

## Definition of Done

- All Phase A tasks committed to the repo
- All Phase B tasks complete on Aliyun: data + app containers healthy, frps running
- All Phase C tasks complete on internal machine: ComfyUI loopback-only, frpc connected
- Phase D end-to-end smoke test passes (Tasks D1 and D2)
- Phase E initiated (ICP filing submitted); Phase 2 switchover completed once filing approves

After Phase D passes, the system is usable internally via `http://<ALIYUN_IP>:8000`. After Phase E2 completes, it's usable publicly via `https://yourdomain.com`.
