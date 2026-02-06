# 端口配置说明

## 当前服务端口

| 服务 | 端口 | 地址 | 说明 |
|------|------|------|------|
| **前端 (Next.js)** | **3001** | http://localhost:3001 | 工作台主界面 |
| 后端 (FastAPI) | 8000 | http://localhost:8000 | API 服务 |
| API 文档 | 8000 | http://localhost:8000/docs | Swagger UI |
| PostgreSQL | 5432 | localhost:5432 | 数据库 |
| Redis | 6379 | localhost:6379 | 缓存/任务队列 |
| MinIO | 9000 | http://localhost:9000 | 对象存储 API |
| MinIO Console | 9001 | http://localhost:9001 | 管理界面 |

## 端口说明

### 前端端口 (3001)

- **默认端口**: 3000
- **实际端口**: 3001（因为 3000 被其他进程占用）
- **自动切换**: Next.js 检测到 3000 被占用时会自动使用 3001
- **访问地址**: http://localhost:3001

> 💡 **提示**: 如果希望固定使用 3000 端口，需要先终止占用 3000 端口的进程，或者修改 `apps/web/package.json` 中的启动脚本。

### 后端端口 (8000)

- **固定端口**: 8000
- **API 基础路径**: http://localhost:8000/api/v1
- **文档地址**: http://localhost:8000/docs

## 快速访问

### 开发环境

```bash
# 前端工作台
http://localhost:3001

# API 文档
http://localhost:8000/docs

# MinIO 管理
http://localhost:9001
用户名: minioadmin
密码: minioadmin
```

## 故障排查

### 前端无法访问

1. 检查 Next.js 是否运行：
   ```bash
   cd apps/web
   npm run dev
   ```

2. 查看终端输出确认实际端口号（可能是 3000 或 3001）

3. 检查端口占用：
   ```powershell
   # Windows
   netstat -ano | findstr :3000
   netstat -ano | findstr :3001
   ```

### 后端 API 无法连接

1. 检查 FastAPI 是否运行：
   ```bash
   cd apps/api
   uvicorn app.main:app --reload --port 8000
   ```

2. 测试 API 健康检查：
   ```bash
   curl http://localhost:8000/health
   ```

3. 检查 CORS 配置（前端地址需要在 `CORS_ORIGINS` 中）

## 修改端口

### 修改前端端口

编辑 `apps/web/package.json`:
```json
{
  "scripts": {
    "dev": "next dev -p 3000"
  }
}
```

### 修改后端端口

编辑 `apps/api/app/core/config.py` 或启动命令：
```bash
uvicorn app.main:app --reload --port 8001
```

记得同时更新前端的 `API_BASE` 配置。
