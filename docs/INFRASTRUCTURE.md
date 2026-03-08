# 基础设施部署选型 - DeerFlow Chraft

本文档列出多租户方案所需的外部服务，以及每项服务的选型建议。

---

## 必须部署的服务

### 1. PostgreSQL（必须）

用途：
- LangGraph checkpoint（对话状态持久化，多实例无状态路由）
- `user_memory` 表（用户长期记忆，替换 `memory.json`）
- `thread_ownership` 表（thread 归属验证）

#### 选项 A：自建（docker-compose，单机开发/小规模生产）

```yaml
# docker/docker-compose-prod.yaml 已包含
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: deerflow
      POSTGRES_USER: deerflow
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
```

环境变量：
```env
POSTGRES_URI=postgresql://deerflow:password@postgres:5432/deerflow
```

#### 选项 B：托管服务（推荐生产）

| 服务 | 优点 | 最低价格参考 |
|------|------|------------|
| **Supabase**（推荐） | 免费计划可用；内置备份；有管理界面 | 免费 / $25/月（Pro） |
| **Neon** | Serverless，按需付费；自动暂停节省成本 | 免费 / $19/月 |
| **Railway** | 一键部署，简单 | ~$5/月 |
| **AWS RDS / Aurora** | 企业级，PITR，高可用 | ~$15/月起 |
| **阿里云 RDS** | 国内低延迟 | ~¥100/月起 |

> **推荐**：开发/测试用 Neon（免费计划），生产用 Supabase Pro 或 AWS RDS。

连接字符串格式：
```env
# Supabase / Neon / RDS 均支持标准 PostgreSQL 连接串
POSTGRES_URI=postgresql://user:password@host:5432/dbname?sslmode=require
```

---

### 2. Redis（可选，仅用于限流）

用途：
- Per-user 请求限流（`rl:{user_id}:{window}` 计数器）
- **不**用于 session 或记忆存储

> **如果不需要限流功能，可以跳过 Redis。** 未设置 `REDIS_URI` 时系统会自动跳过限流。

#### 选项 A：自建

```yaml
services:
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
```

```env
REDIS_URI=redis://redis:6379
```

#### 选项 B：托管服务

| 服务 | 推荐场景 |
|------|---------|
| **Upstash Redis** | Serverless，按请求计费，有免费计划 |
| **Redis Cloud** | 官方托管，30MB 免费 |
| **AWS ElastiCache** | 企业级，适合已在 AWS 的团队 |

```env
# Upstash 示例
REDIS_URI=redis://:password@us1-xxx.upstash.io:6379
```

---

## 共享文件存储（PVC）

用途：
- `users/{user_id}/skills/custom/`（用户私有 skills）
- `users/{user_id}/agents/`（用户自定义 agents）
- `users/{user_id}/secrets.enc`（用户加密 API keys）
- `threads/{thread_id}/user-data/`（上传文件、输出文件）
- `skills/public/`（全局公共 skills）

#### 单机部署（bind mount，默认）

无需额外服务。docker-compose 中直接 bind mount 宿主机目录：

```yaml
volumes:
  deer_flow_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/deer-flow   # 宿主机目录，自行备份
```

> 单机部署无需额外配置，现有行为不变。

#### 多节点部署（NFS/EFS/Ceph）

| 方案 | 适用场景 |
|------|---------|
| **NFS**（自建） | 内网多节点，成本低 |
| **AWS EFS** | AWS 环境，自动多节点共享，支持 AWS Backup |
| **阿里云 NAS** | 阿里云环境 |
| **Longhorn**（K8s） | K8s 集群，开源，提供 ReadWriteMany |

> 多节点时 PVC 必须支持 `ReadWriteMany`（RWX）。

---

## 环境变量汇总

```env
# ===== 认证（必须配置，AUTH_ENABLED=true 时）=====
AUTH_ENABLED=false                    # 改为 true 开启认证
JWT_SECRET_KEY=your-secret-key        # 与外部颁发 JWT 的系统共享
JWT_ALGORITHM=HS256                   # HS256 或 RS256
JWT_USER_ID_CLAIM=sub                 # JWT payload 中 user_id 的字段名

# ===== 用户 Secrets 加密主密钥（开启 secrets 管理时必须）=====
SECRETS_MASTER_KEY=                   # 32 字节 base64，用 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 生成

# ===== PostgreSQL（必须）=====
POSTGRES_URI=postgresql://deerflow:password@postgres:5432/deerflow

# ===== Redis（可选，用于限流）=====
REDIS_URI=redis://redis:6379
RATE_LIMIT_REQUESTS=100               # 每用户每窗口最大请求数
RATE_LIMIT_WINDOW=60                  # 统计窗口（秒）
```

---

## 快速启动（开发模式）

开发模式最小化配置：只需本地 PostgreSQL，无需 Redis，无需认证。

```bash
# 1. 启动 PostgreSQL（docker-compose dev 已包含）
docker compose -f docker/docker-compose-dev.yaml up postgres -d

# 2. 设置环境变量
export POSTGRES_URI=postgresql://deerflow:deerflow@localhost:5432/deerflow
export AUTH_ENABLED=false   # 不开启认证，user_id 默认 "default"

# 3. 正常启动项目
make dev
```

---

## 生产部署检查清单

- [ ] PostgreSQL 已配置，`POSTGRES_URI` 已设置
- [ ] 数据库已初始化表结构（首次启动自动执行）
- [ ] `JWT_SECRET_KEY` 已生成并与外部认证系统共享
- [ ] `SECRETS_MASTER_KEY` 已生成（如需用户 API key 管理功能）
- [ ] 共享文件存储已挂载（多节点时使用 NFS/EFS）
- [ ] PostgreSQL 定期备份已配置（pg_dump cron 或托管服务自动备份）
- [ ] Redis 已配置（如需限流功能）
- [ ] Nginx `Authorization` header 透传已确认
