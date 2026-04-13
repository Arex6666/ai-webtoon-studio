# Aliyun + 内网混合部署设计

**日期**：2026-04-13
**范围**：把 AI Webtoon Studio 部署到阿里云北京服务器（对外）+ 家里 NAT 内网 GPU 机（ComfyUI），两者通过 FRP 反向隧道连通。

---

## 1. 背景与目标

当前仓库是本地开发形态：前后端、数据库、对象存储、ComfyUI 全跑在一台开发机上。现在要把它上线到公网，面向小规模（数十到数百）用户使用。

**核心约束**

- **GPU 在家里**：ComfyUI 和本地图像/视频模型必须跑在内网 GPU 机上（显卡在那儿），这台机器在家用 WiFi NAT 后面，没有公网 IP，也做不了端口映射。
- **公网入口在阿里云**：为了给外部用户提供稳定访问，需要一台公网可达的机器做网站入口。区域选北京（大陆），受 ICP 备案约束。
- **小规模对外**：用户数数十到数百，有偶发并发渲染。最终的产出图/视频会被公网用户拉取展示。
- **后期频繁改代码**：上线后仍会持续修改服务器上的源码。

**设计目标**

1. 用户从公网能正常访问前端、API、拉取产物图片/视频
2. 渲染 job 从 Aliyun 后端可达内网 ComfyUI，产物能安全回流到 Aliyun 存储
3. 内网机**不开任何入站端口**，完全 NAT 后面也能工作
4. 部署和后期维护尽可能简单，支持热改代码
5. 能在备案未完成的阶段就把系统内部跑通

**非目标**

- 不做 HA / 多活
- 不做自动伸缩
- 不做多 GPU 机集群（单台内网 GPU 机够用）
- 不做 CI/CD 流水线（后期要加再说）

---

## 2. 顶层架构

```
                             Internet / 用户
                                   │
                                   ▼
            ┌────────────────────────────────────────────┐
            │  Aliyun 北京（公网 IP，阶段 2 后接域名+TLS）│
            │                                            │
            │   Nginx (80/443，或阶段 1 的 8000)         │
            │    ├─ /           → Next.js (3001)         │
            │    ├─ /api/*, /ws → FastAPI (8000)         │
            │    └─ /media/*    → MinIO (9000)           │
            │                                            │
            │   Celery worker  (image/video/export 队列) │
            │                                            │
            │   Postgres · Redis · MinIO                 │
            │                                            │
            │   frps  (监听 7000, TLS+token)             │
            └──────────────────────▲─────────────────────┘
                                   │  FRP over TLS
                                   │  内网机主动外拨
                                   │  Aliyun 侧暴露为 127.0.0.1:18188
            ┌──────────────────────┴─────────────────────┐
            │   内网 GPU 机（家里 WiFi 后面，纯出站）    │
            │                                            │
            │   ComfyUI (127.0.0.1:8188)                 │
            │   + 本地模型（ckpt/LoRA/IP-Adapter/VAE）   │
            │   + SVD / AnimateDiff 等视频节点           │
            │                                            │
            │   frpc ──主动连──→ aliyun:7000             │
            └────────────────────────────────────────────┘
```

### 职责划分

| 组件 | 位置 | 对外暴露 |
|---|---|---|
| Nginx | Aliyun | 80/443（阶段 2）或 8000（阶段 1） |
| Next.js | Aliyun | 仅经 Nginx |
| FastAPI | Aliyun | 仅经 Nginx（`/api`、`/ws`） |
| Celery worker | Aliyun | 否 |
| Postgres | Aliyun | 否（容器内网） |
| Redis | Aliyun | 否（容器内网） |
| MinIO | Aliyun | 经 Nginx `/media`（presigned URL） |
| frps | Aliyun | 7000（仅 frp 握手；token+TLS） |
| ComfyUI | 内网机 | 只监听 127.0.0.1 |
| frpc | 内网机 | 无（主动外拨） |

---

## 3. 网络连接：FRP 反向隧道

### 原理
内网机主动连阿里云的 frps 控制端口（7000），建立一条常驻 TLS 通道。frps 把本地 `18188` 反代到这条通道另一头的内网 `8188`。Aliyun 上的 Celery worker 只需把 `COMFYUI_URL=http://127.0.0.1:18188`，`comfyui_client.py` 代码不需要改。

### 关键配置

**`frps.toml`（Aliyun）**
```toml
bindAddr  = "0.0.0.0"
bindPort  = 7000
auth.method = "token"
auth.token  = "<32 字节强随机 token>"
transport.tls.force = true
# 限制客户端只能暴露这几个端口
allowPorts = [{ start = 18188, end = 18188 }]
```

**`frpc.toml`（内网机）**
```toml
serverAddr = "<aliyun-public-ip>"
serverPort = 7000
auth.method = "token"
auth.token  = "<同 frps>"
transport.tls.enable = true

[[proxies]]
name      = "comfyui"
type      = "tcp"
localIP   = "127.0.0.1"
localPort = 8188
remotePort = 18188
```

### 安全要点

1. **内网机零入站**：家里路由器不做任何端口映射。
2. **ComfyUI 只监听 loopback**：`127.0.0.1:8188`，局域网其他设备也访问不到。
3. **Aliyun 上 18188 不对公网**：frps 启动时该端口只绑 loopback；阿里云安全组也不放行 18188。只有 Aliyun 本机上的 Celery worker（同机）可以访问。
4. **7000 端口保护**：强 token + 强制 TLS。如果家里公网 IP 稳定，阿里云安全组可以再加一层 IP 白名单。
5. **frp 版本**：使用较新版本（≥ 0.52），对 TLS 和 token 支持更完善。

### 故障恢复
- frpc 启动配 `restart=always`（systemd 或 docker `restart: unless-stopped`）
- frp 自带心跳 + 自动重连，WiFi 抖动 / 路由重启后 10–30s 恢复
- 隧道断时，新建渲染 job 会失败；已入 MinIO 的产物 + 数据库 + 前端仍正常

---

## 4. 部署方式：Docker Compose + 卷挂载 + 热重载

### 为什么选这个

- 源码挂载进容器，改 `.py` 后 uvicorn `--reload` 自动重启
- 改前端 Next.js dev 模式 HMR 或生产 `next start`（按需选）
- 所有依赖在容器里，不污染宿主机 Python/Node 环境
- `docker compose logs -f` 一条命令看所有服务日志
- 整坨搬到别的机器用同一个 compose 文件就能起

### 相对现有 `docker/docker-compose.yml` 的调整

现有文件是开发版，需要做生产加固：

1. **所有服务加 `restart: unless-stopped`**
2. **数据卷持久化到宿主机固定目录**（便于备份和迁移）
   - `postgres_data` → `/srv/webtoon/data/postgres`
   - `minio_data`    → `/srv/webtoon/data/minio`
   - `redis_data`    → `/srv/webtoon/data/redis`
3. **环境变量独立到 `.env.prod`**
   - DB 密码、MinIO 密码改为强随机（不能用 `postgres/postgres`、`minioadmin`）
   - 生成独立 JWT secret
   - 填入 ARK_API_KEY / DOUBAO_API_KEY / TONGYI_API_KEY
   - 新增 `COMFYUI_URL=http://host.docker.internal:18188`（或用 `network_mode: host` 的方式让 worker 访问宿主机 loopback）
4. **加 Nginx 服务**：反向代理 + TLS（阶段 2）+ 客户端 IP 转发
5. **加 frps 服务**（或宿主机上直接跑 systemd unit）
6. **Next.js 可选切生产模式**：如果不希望公网用户看到 dev 模式红屏错误，改成 `next build && next start`（但这会牺牲前端热改）
7. **CORS_ORIGINS** 改成实际域名或 IP

### worker 访问 frps 暴露的 127.0.0.1:18188

有三种做法，选**第二种**：

1. ~~worker 用 `host` 网络模式~~：破坏容器隔离
2. **frps 用 `host` 网络模式运行** → 18188 落到宿主机 loopback → worker 通过 `host.docker.internal:18188` 访问（Linux 下需加 `extra_hosts: "host.docker.internal:host-gateway"`）
3. ~~frps 也容器化但 publish 18188 到宿主机~~：需要小心不要误绑到 0.0.0.0

### 目录规划（Aliyun）

```
/srv/webtoon/
├── source/              # git clone 的仓库
│   ├── apps/
│   ├── docker/
│   └── ...
├── data/                # 持久化数据（不进 git）
│   ├── postgres/
│   ├── minio/
│   └── redis/
├── config/
│   ├── .env.prod
│   ├── nginx/           # nginx 配置 + certbot 证书
│   └── frp/frps.toml
└── logs/                # 容器日志（docker logging driver 落到这里）
```

---

## 5. 阶段化上线（备案并行）

### 阶段 1：备案期间的 IP 内测

**状态**：域名还没买 / 备案中，仅限你和团队用浏览器访问做集成测试。

- Nginx 监听 `8000`（或其他非标 HTTP 端口，避开平台对未备案 80 的拦截）
- 仅 HTTP，无证书
- CORS_ORIGINS 设 `http://<aliyun-ip>:8000`
- Next.js 构建时 `NEXT_PUBLIC_API_BASE_URL=http://<aliyun-ip>:8000`、`NEXT_PUBLIC_WS_BASE_URL=ws://<aliyun-ip>:8000`
- MinIO presigned URL 也指向 `http://<aliyun-ip>:8000/media/`
- 阿里云安全组放行 8000 给公网（或只给团队 IP）
- 所有服务、FRP 隧道、ComfyUI 都跑起来，跑通端到端一次渲染

### 阶段 2：备案通过后切换

- 买域名并完成 ICP 备案（阿里云控制台走流程）
- DNS A 记录指到 Aliyun 公网 IP
- Nginx 启 443，certbot 签 Let's Encrypt 证书（`--standalone` 或 `--webroot`）
- 80 → 443 301 跳转
- 改 `.env.prod`：
  - `NEXT_PUBLIC_API_BASE_URL=https://yourdomain.com`
  - `NEXT_PUBLIC_WS_BASE_URL=wss://yourdomain.com`
  - `CORS_ORIGINS=["https://yourdomain.com"]`
- Next.js 重新 build；Nginx reload
- 阿里云安全组关 8000，只放 80/443

代码本身两阶段无改动，只有环境变量 + Nginx server 块 + 防火墙 3 处差异。

---

## 6. 数据流（一次完整渲染）

```
1. 浏览器 → HTTPS/HTTP → Nginx → FastAPI
     创建 RenderJob → 投递到 Redis 队列

2. Celery worker（Aliyun 本机）消费 job
     ↓
3. worker 构造 ComfyUI workflow JSON
     POST http://127.0.0.1:18188/prompt
     ↓（经 frps → FRP 隧道 → frpc）
4. 内网 ComfyUI 收到任务，GPU 推理

5. worker 轮询 http://127.0.0.1:18188/history/{prompt_id}

6. 推理完成，worker 通过同一通道拉回产物（PNG / MP4）
     这是**家宽上行消耗的唯一时刻**（通常 2–50 MB）

7. worker 把产物上传到 Aliyun 本机 MinIO（容器内网，很快）

8. worker 写 Postgres，发 WS 事件（layerpack_ready / video_job_status）

9. 浏览器收到 WS 事件 → 用 presigned URL 从 Nginx /media/ 拉图显示
```

### 带宽计算（家宽 100 Mbps 上行）

| 产物类型 | 大小 | 过隧道耗时 |
|---|---|---|
| 单张 PNG | 2–5 MB | 0.2–0.5 s |
| LayerPack（5 张 PNG） | 10–25 MB | 1–2.5 s |
| 短视频 MP4（3–5 秒） | 15–40 MB | 1.5–4 s |

视频生成本身 30 s–几分钟，传输时间几乎可忽略。

---

## 7. 故障模式与可观测

| 故障 | 影响面 | 恢复 |
|---|---|---|
| 家里 WiFi 抖动 / 路由器重启 | 正在渲染的 job 可能失败；新 job 提交后排队 | frpc 自动重连（秒级）；worker job 重试机制（仓库已有） |
| 内网机关机 / ComfyUI crash | 所有渲染失败 | 前端展示 job_failed；API / 已存 MinIO 的产物不受影响 |
| Aliyun 宕机 | 整站不可用 | docker `restart: unless-stopped` 自动拉起；持久卷在宿主机盘上 |
| 家里公网 IP 变了 | 无影响（连接是内网主动发起） | 无 |
| Aliyun 公网 IP 变了 | frpc 连不上 | 改 frpc `serverAddr` 重启；建议买阿里云**弹性公网 IP**避免漂移 |
| 阿里云磁盘挂了 | Postgres / MinIO 丢数据 | 定时 `pg_dump` + MinIO bucket 备份到阿里云 OSS（后续加） |

### 可观测

- `docker compose logs -f api worker web nginx frps`
- Celery job 状态直接读 `RenderJob` 表（已有 status、logs 字段）
- FRP 自带 dashboard（frps 配置打开 `webServer`，本地 7500 端口，只在 loopback 监听，SSH 转发访问）
- ComfyUI web UI 不对外，临时调试用 `ssh -L 8188:127.0.0.1:18188 aliyun`

---

## 8. 上线清单（高层，细节留给 implementation plan）

### Aliyun 侧（一次性）
1. 买北京 ECS（2c4g 起，100 GB 数据盘），绑定弹性公网 IP
2. 装 Docker + Docker Compose plugin
3. 建 `/srv/webtoon/{source,data,config,logs}` 目录结构
4. `git clone` 仓库到 `/srv/webtoon/source`
5. 在 `docker/` 下加 `docker-compose.prod.yml`（阶段 1 用）+ `nginx/` + `frp/` 配置
6. 写 `.env.prod`，强随机密码、JWT、token 都生成好
7. `docker compose -f docker-compose.prod.yml up -d postgres redis minio`
8. `alembic upgrade head` 初始化表
9. `docker compose up -d api worker web nginx frps`

### 内网机侧（一次性）
1. 装好 ComfyUI + 模型文件（本地路径固定）
2. ComfyUI 启动参数加 `--listen 127.0.0.1 --port 8188`
3. 装 frpc（二进制 + systemd 或 docker）
4. 写 `frpc.toml`，启动服务
5. 验证 Aliyun 上 `curl http://127.0.0.1:18188/system_stats` 能拿到 ComfyUI 响应

### 端到端验收
1. Aliyun 浏览器（`http://<ip>:8000`）注册/登录
2. 建项目 → 写段脚本 → 生成分镜 → 渲染一个 panel
3. 观察 WS 事件流、MinIO 中产物、RenderJob.status
4. 触发一次视频生成，确认产物回流

### 阶段 2 切换清单（备案通过后）
1. DNS A 记录指 Aliyun IP
2. 配置 Nginx 443 server 块 + certbot 签证
3. 改 `.env.prod` 的 URL 相关变量
4. Next.js 重新 build
5. 阿里云安全组关 8000，开 443
6. 浏览器访问 `https://yourdomain.com` 验证

---

## 9. 风险与权衡

| 风险 | 评估 | 处理 |
|---|---|---|
| 家里上行带宽不够 | 100 Mbps 上行，单视频 3 s 可接受；若用户高并发视频可能堆积 | 短期可忽略；超过 B 规模再上多 GPU 机或 CDN |
| 家宽 IP 封/限 ToS | 运营商一般不限制出站 TLS | 低；若真被限制换 FRP 协议（kcp/wss） |
| 阿里云北京备案慢 | 2–4 周，影响公开上线时间 | 用阶段 1 IP 方案内部跑通，备案通过直接切 |
| ComfyUI 自己更新 breaking | 模型或节点版本变动 | 在内网机维护一份固定模型版本；workflow JSON 做版本兼容 |
| JWT secret / MinIO 密码泄漏 | 直接拿到全部用户数据 | `.env.prod` 权限 600，不入 git；定期轮换 |
| 备份缺失 | Aliyun 磁盘故障数据全丢 | 后续加 `pg_dump` + MinIO → OSS 的定时任务（本 spec 不含，列为下一步） |

---

## 10. 本设计不包含 / 留给后续

- **备份策略**：Postgres 定时 dump、MinIO 到阿里云 OSS
- **监控告警**：Prometheus / Grafana / Uptime 监测
- **CI/CD**：push 到 main 自动部署
- **多 GPU 机扩容**
- **CDN 接入**：MinIO 前再套一层 CDN 加速海外访问
- **用户配额 / 限流**
- **日志集中**：Loki / Elastic

这些都是 B 规模以上才需要的，等第一轮稳定运行再排进 spec。
