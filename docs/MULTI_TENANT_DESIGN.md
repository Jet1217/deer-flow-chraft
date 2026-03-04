# 多租户隔离方案 - DeerFlow Chraft

## 背景

用户注册在外部系统完成，本项目只需：
1. 通过 JWT 验证调用身份，防止恶意访问
2. 根据 JWT 中的 `user_id` 隔离 Skills、Keys、Assets、Long Memory
3. 向后兼容（`AUTH_ENABLED=false` 时行为不变）

---

## 现状评估

当前隔离级别是 **Thread 维度**，不是 User 维度：

| 资源 | 当前状态 | 问题 |
|------|----------|------|
| Skills | 全局共享 `skills/{public,custom}/` | 用户 A 安装的 skill 所有人可用 |
| API Keys | 单一 `.env` / `config.yaml` | 所有用户共用同一套密钥 |
| Assets | Thread 隔离 `threads/{thread_id}/` | 无用户归属，thread_id 猜出来就能访问 |
| Long Memory | 单一 `memory.json` | 所有对话共写同一份记忆 |
| Extensions Config | 单一 `extensions_config.json` | skill 开关全局影响 |
| Agents | 单一 `agents/` 目录 | 所有自定义 agent 全局可见 |
| MCP Tools | 全局进程级缓存 | 不同用户 MCP 配置互相污染 |

---

## 架构总览

```
外部系统颁发 JWT（含 user_id）
        ↓
[Nginx] Authorization: Bearer <JWT> 透传（需确认 header 不被覆写）
        ↓                                    ↓
[Gateway API :8001]                [LangGraph Server :2024]
  FastAPI AuthMiddleware               langgraph_handler:auth
  → request.state.user_id             → config.metadata["owner"]
        ↓                                    ↓
  用户命名空间路径                       make_lead_agent(user_id=...)
  users/{user_id}/...                   ├── MemoryMiddleware(user_id)
                                        ├── load_skills(user_id)
                                        └── get_available_tools(user_id)
                                                ↓
                                        _resolve_key(key_name, user_id)
                                        ├── users/{user_id}/secrets.enc  ← 用户自有 key
                                        └── 系统 .env                    ← 平台默认 key
```

---

## 文件系统结构

```
{base_dir}/                           # 原有布局不变
├── threads/                          # 全局 threads（thread_id 归属记录在 PostgreSQL）
│   └── {thread_id}/
│       └── user-data/
│           ├── workspace/
│           ├── uploads/
│           └── outputs/
│
├── users/                            # 新增：用户命名空间
│   └── {user_id}/
│       ├── USER.md                   # 用户 profile
│       ├── extensions_config.json    # 用户的 skill/MCP 开关（含 MCP server 凭据）
│       ├── secrets.enc               # 用户 API Keys（Fernet 加密，新增）
│       ├── skills/
│       │   └── custom/               # 用户安装的私有 skills
│       └── agents/
│           └── {agent_name}/         # 用户自定义 agents
│               ├── config.yaml
│               └── SOUL.md
│
└── skills/public/                    # 全局公共 skills（只读共享，不变）
```

> **存储选型原则**：
>
> | 数据类型 | 存储方案 | 原因 |
> |---------|---------|------|
> | 对话状态（checkpoint）| PostgreSQL | LangGraph 原生支持，多实例无状态路由 |
> | 长期记忆（memory）| PostgreSQL `user_memory` 表 | 多写者高频更新，需 MVCC 一致性；进程内 TTL 缓存 + 到期查 DB |
> | Thread 归属 | PostgreSQL `thread_ownership` 表 | 需原子性，NFS 无法保证并发写幂等 |
> | Skills/Agents/Secrets 文件 | 共享 PVC（NFS/EFS） | 写一次读多次，不存在并发写竞争；文件永久保存在网络存储上 |
> | Uploads/Outputs 文件 | 共享 PVC（NFS/EFS） | 二进制文件，按 thread 隔离，容器重启不丢失 |
>
> **为什么 memory 不用共享 PVC**：即使文件在 NFS 上，各实例的进程内 TTL 缓存仍各自独立，
> Instance B 的缓存不会因为 Instance A 写了新文件而自动失效，下次对话仍会注入旧记忆。
> PostgreSQL 则无此问题：TTL 到期后直接查 DB，任意实例写入其他实例立即可见。

---

## 环境变量

```env
# 认证
AUTH_ENABLED=true            # false = 关闭认证（向后兼容，user_id 默认 "default"）
JWT_SECRET_KEY=<secret>      # 与外部系统共享的签名密钥（HS256）
JWT_ALGORITHM=HS256          # 或 RS256（公钥验证）
JWT_USER_ID_CLAIM=sub        # JWT claim 字段名，默认 "sub"

# 用户 Secrets 加密主密钥
SECRETS_MASTER_KEY=<32-byte-base64>   # 用于加/解密 users/{id}/secrets.enc

# 平台默认 API Keys（当用户未配置自己的 key 时使用）
TAVILY_API_KEY=...
FIRECRAWL_API_KEY=...
OPENAI_API_KEY=...
# ... 其他平台提供的默认 keys
```

---

## Skill Key 管理架构

### 设计原则

- **内置 public skills**：平台提供默认 key（系统 `.env`），用户可选择覆盖为自己的 key
- **用户 custom skills 及 MCP 服务器**：必须用户自己提供 key，平台不承担费用
- **完全隔离**：每个用户的 key 独立存储、加密，互不可见
- **优先级**：用户 key > 平台默认 key（降级，不报错）

### Key 分类与解析优先级

```
工具类型                          Key 解析链
─────────────────────────────     ─────────────────────────────────────────
系统工具（Tavily, Firecrawl）     用户 secrets.enc → 平台 .env → 报错/降级
MCP 服务器工具                    用户 extensions_config.json OAuth 凭据（纯用户自有）
Sandbox 代码执行（Python）        用户 secrets.enc 注入为 sandbox env vars
用户 custom skill 依赖工具        同上，必须用户自己配置
```

### `users/{user_id}/secrets.enc` 格式

整体文件用 `cryptography.fernet.Fernet` 加密，明文为 JSON：

```json
{
  "TAVILY_API_KEY": "sk-user-tavily-xxx",
  "FIRECRAWL_API_KEY": "fc-user-xxx",
  "OPENAI_API_KEY": "sk-user-openai-xxx",
  "ANTHROPIC_API_KEY": "ak-user-xxx",
  "CUSTOM_IMAGE_API_KEY": "img-user-xxx"
}
```

加密方案：
- 主密钥 `SECRETS_MASTER_KEY` 存于系统环境变量（Docker secret 或平台密钥管理）
- `Fernet(SECRETS_MASTER_KEY).encrypt(json.dumps(secrets).encode())`
- 读时 `Fernet(SECRETS_MASTER_KEY).decrypt(file.read())`
- 原子写：先写 `.tmp` 再 `rename`

### Key 解析函数（新建 `backend/src/auth/secrets.py`）

```python
def load_user_secrets(user_id: str | None) -> dict[str, str]:
    """加载用户 secrets，解密返回 {key_name: key_value}"""
    if not user_id:
        return {}
    secrets_file = get_paths().user_secrets_file(user_id)
    if not secrets_file.exists():
        return {}
    master_key = os.environ["SECRETS_MASTER_KEY"]
    return json.loads(Fernet(master_key).decrypt(secrets_file.read_bytes()))

def resolve_api_key(key_name: str, user_id: str | None) -> str | None:
    """解析 key：用户优先，平台兜底"""
    if user_id:
        user_secrets = load_user_secrets(user_id)
        if key_name in user_secrets:
            return user_secrets[key_name]
    return os.environ.get(key_name)   # 平台默认
```

### Gateway API 端点（新增，`routers/secrets.py`）

```
GET  /api/secrets         → 返回用户已配置的 key 名称列表（不返回值）
POST /api/secrets         → 写入/更新一个 key，Body: {key_name, key_value}
DELETE /api/secrets/{name} → 删除一个 key
```

### 工具加载改造（`tools/tools.py`）

当前 `get_available_tools()` 通过反射加载 LangChain tool 单例，key 在构造时固化。
需改为 **per-user 实例化 + 缓存**：

```python
_user_tool_cache: dict[str, list[BaseTool]] = {}   # user_id → tools

def get_available_tools(..., user_id: str | None = None) -> list[BaseTool]:
    cache_key = f"{user_id}|{groups}|{include_mcp}"
    if cache_key in _user_tool_cache:
        return _user_tool_cache[cache_key]

    user_secrets = load_user_secrets(user_id)
    tools = []
    for tool_config in config.tools:
        # 若工具定义了 key_env_var 字段，用用户 key 覆盖环境变量后实例化
        effective_key = user_secrets.get(tool_config.key_env_var) or os.environ.get(tool_config.key_env_var)
        tool = _instantiate_tool(tool_config, api_key=effective_key)
        tools.append(tool)

    _user_tool_cache[cache_key] = tools
    return tools
```

> **注意**：`config.yaml` 中的工具定义需新增可选字段 `key_env_var: TAVILY_API_KEY`，
> 用于标识该工具使用哪个环境变量名查找 key。

### MCP Tools per-user 缓存（`mcp/cache.py`）

当前全局 `_mcp_tools_cache: list[BaseTool]` 改为：
```python
_mcp_tools_cache: dict[str, list[BaseTool]] = {}   # user_id → tools

def get_user_mcp_tools(user_id: str | None) -> list[BaseTool]:
    """按用户的 extensions_config.json 加载 MCP tools，带 per-user 缓存"""
    cache_key = user_id or "default"
    if cache_key in _mcp_tools_cache:
        return _mcp_tools_cache[cache_key]

    # 读用户的 extensions_config（含用户自己的 MCP 服务器凭据）
    config_path = get_paths().user_extensions_config_file(user_id) if user_id else None
    extensions_config = ExtensionsConfig.from_file(config_path)
    tools = _init_mcp_tools(extensions_config.get_enabled_mcp_servers())
    _mcp_tools_cache[cache_key] = tools
    return tools
```

### Sandbox 环境变量注入（`sandbox/middleware.py`）

用户代码在 sandbox 执行时，需要能访问用户自己的 key：

```python
class SandboxMiddleware(AgentMiddleware):
    def __init__(self, lazy_init=True, user_id=None):
        self._user_id = user_id

    def _acquire_sandbox(self, thread_id: str) -> str:
        user_env = load_user_secrets(self._user_id)   # 解密注入
        provider = get_sandbox_provider()
        return provider.acquire(thread_id, extra_env=user_env)
```

`SandboxProvider.acquire()` 将 `extra_env` 传给 sandbox 容器/进程，
用户在 sandbox Python 脚本里 `os.environ["TAVILY_API_KEY"]` 即可获取自己的 key。

---

## 实现步骤

### Step 1：Auth 模块（新建 `backend/src/auth/`）

**`backend/src/auth/jwt_utils.py`**
- `verify_jwt(token: str) -> str`：用 `PyJWT` 验证签名，返回 `user_id`（`payload[JWT_USER_ID_CLAIM]`）
- `_SAFE_USER_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")`：防止路径注入
- `get_user_id_from_request(request)` → `AUTH_ENABLED=false` 时返回 `"default"`

**`backend/src/auth/gateway_middleware.py`**（Starlette BaseHTTPMiddleware）
- 跳过 `/health` 路径
- 从 `Authorization: Bearer <token>` 提取 token → `verify_jwt` → `request.state.user_id`
- 失败返回 401

**`backend/src/auth/langgraph_handler.py`**（LangGraph Platform Auth）
```python
from langgraph_sdk import Auth
auth = Auth()

@auth.authenticate
async def authenticate(authorization: str | None) -> dict:
    # 验证 JWT，返回 {"id": user_id}
    ...

@auth.on
async def add_owner(ctx, value):
    # 写入 thread metadata: {"owner": ctx.user["id"]}
    # LangGraph 自动按 owner 过滤线程列表，实现线程级隔离
    metadata = ctx.metadata or {}
    metadata["owner"] = ctx.user["id"]
    ctx.metadata = metadata
```

**`backend/src/auth/secrets.py`** — 用户 secrets 加解密（见上节）

**`backend/src/auth/__init__.py`** — 导出 FastAPI dependency：
```python
async def get_current_user_id(request: Request) -> str:
    return getattr(request.state, "user_id", "default")
```

---

### Step 2：PathsConfig 扩展（`backend/src/config/paths.py`）

在现有 `Paths` 类中**追加方法**，不修改已有方法（向后兼容）：

```python
_SAFE_USER_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")

# 用户命名空间（文件路径）
def user_root(self, user_id: str) -> Path
def user_md_file_path(self, user_id: str) -> Path
def user_agents_dir(self, user_id: str) -> Path
def user_agent_dir(self, user_id: str, name: str) -> Path
def user_skills_dir(self, user_id: str) -> Path               # .../skills/custom/
def user_extensions_config_file(self, user_id: str) -> Path   # .../extensions_config.json
def user_secrets_file(self, user_id: str) -> Path             # .../secrets.enc（新增）
```

> **不包含** `user_memory_file`、`user_agent_memory_file`、`thread_owner_file` 等路径方法，
> 因为长期记忆和 thread 归属均存入 PostgreSQL（见 Step 3 和高并发章节）。

---

### Step 3：Memory 系统迁移至 PostgreSQL

**为什么不用 `memory.json` 文件？**

多实例场景下文件存储有三个无法解决的问题：
1. **缓存不一致**：各 LangGraph 实例独立维护进程内 TTL 缓存，Instance B 可能读到 Instance A 写完之前的旧版本
2. **NFS 锁不可靠**：`fcntl.flock` 在共享卷（NFS/PVC）上行为未定义，高负载下可能失效
3. **mtime 精度问题**：NFS 时间戳精度不足，mtime-based 缓存失效机制无法保证正确性

**解决方案：PostgreSQL `user_memory` 表**

```sql
CREATE TABLE user_memory (
    user_id    TEXT        NOT NULL,
    agent_name TEXT        NOT NULL DEFAULT '',   -- '' 表示通用记忆，否则为 agent 名
    data       JSONB       NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, agent_name)
);
```

**`backend/src/agents/memory/db.py`**（新建，封装 PostgreSQL 操作）

```python
async def get_memory(user_id: str, agent_name: str = "") -> dict:
    row = await db.fetchrow(
        "SELECT data FROM user_memory WHERE user_id=$1 AND agent_name=$2",
        user_id, agent_name
    )
    return dict(row["data"]) if row else {}

async def save_memory(user_id: str, data: dict, agent_name: str = "") -> None:
    """原子 upsert，无需分布式锁"""
    await db.execute(
        """
        INSERT INTO user_memory (user_id, agent_name, data, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (user_id, agent_name)
        DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
        """,
        user_id, agent_name, json.dumps(data)
    )
```

**`backend/src/agents/memory/updater.py`** 修改：
- 移除所有文件路径逻辑（`_get_memory_file_path`、`fcntl.flock`、mtime 检测）
- `_memory_cache` key 改为 `(user_id, agent_name)` → TTL 缓存，过期时重新查 DB
- `get_memory_data(agent_name=None, user_id=None)` → 调用 `db.get_memory(user_id, agent_name)`
- `MemoryUpdater.update_memory(..., user_id=None)` → 调用 `db.save_memory(user_id, data)`

**`backend/src/agents/memory/queue.py`**
- `ConversationContext` 添加字段 `user_id: str | None = None`
- `add(thread_id, messages, agent_name=None, user_id=None)` 透传

**`backend/src/agents/middlewares/memory_middleware.py`**
- `__init__(self, agent_name=None, user_id=None)` → 保存 `self._user_id`
- `queue.add(..., user_id=self._user_id)`

---

### Step 4：Lead Agent 注入 user_id（`backend/src/agents/lead_agent/agent.py`）

```python
def make_lead_agent(config: RunnableConfig):
    user_id = (
        config.get("metadata", {}).get("owner")
        or config.get("configurable", {}).get("user_id")
        or None
    )
    ...
    tools = get_available_tools(..., user_id=user_id)   # 携带 user_id 解析 key

def _build_middlewares(config, model_name, agent_name=None, user_id=None):
    ...
    middlewares.append(SandboxMiddleware(user_id=user_id))    # 注入 sandbox env
    middlewares.append(MemoryMiddleware(agent_name=agent_name, user_id=user_id))
```

---

### Step 5：agents_config 模块 user_id 支持（`backend/src/config/agents_config.py`）

> **原计划遗漏**：原计划只改了 router，但 `make_lead_agent` 直接调用模块层函数，需在模块层也加 user_id。

```python
def load_agent_config(name: str | None, user_id: str | None = None) -> AgentConfig | None:
    agent_dir = (get_paths().user_agent_dir(user_id, name) if user_id
                 else get_paths().agent_dir(name))
    ...

def load_agent_soul(agent_name: str | None, user_id: str | None = None) -> str | None:
    agent_dir = (get_paths().user_agent_dir(user_id, agent_name) if user_id
                 else get_paths().agent_dir(agent_name))
    ...

def list_custom_agents(user_id: str | None = None) -> list[AgentConfig]:
    agents_dir = (get_paths().user_agents_dir(user_id) if user_id
                  else get_paths().agents_dir)
    ...
```

`make_lead_agent` 里调用改为 `load_agent_config(agent_name, user_id=user_id)`。

---

### Step 6：Skills Loader 用户隔离（`backend/src/skills/loader.py`）

```python
def load_skills(skills_path=None, use_config=True, enabled_only=False, user_id=None):
    # 1. 加载全局 public skills（行为不变）
    # 2. 若 user_id：追加扫描 paths.user_skills_dir(user_id)（私有 skills）
    # 3. 加载 enabled 状态：
    #    - 若 user_id 且 user_extensions_config_file 存在 → 读用户配置
    #    - 否则回退全局 ExtensionsConfig.from_file()
```

---

### Step 7：Tools 加载 + MCP per-user 缓存

- `backend/src/tools/tools.py`：`get_available_tools(..., user_id=None)` 见"Key 管理"节
- `backend/src/mcp/cache.py`：全局缓存 → per-user 缓存 `dict[str, list[BaseTool]]`
- `backend/src/config/tool_config.py`：工具定义模型新增可选字段 `key_env_var: str | None`

---

### Step 8：Gateway 路由注入 user_id（`backend/src/gateway/`）

**`backend/src/gateway/app.py`**
- 若 `AUTH_ENABLED=true`：`app.add_middleware(AuthMiddleware)`

各路由通过 FastAPI dependency 获取 `user_id: str = Depends(get_current_user_id)`：

| 路由文件 | 改动 |
|---------|------|
| `routers/memory.py` | `get_memory_data(user_id=user_id)` |
| `routers/agents.py` | `list_custom_agents(user_id=user_id)`；用户 agents 目录 |
| `routers/skills.py` | `load_skills(user_id=user_id)`；安装到用户 skills 目录；写用户 extensions_config |
| `routers/uploads.py` | 上传前 `INSERT INTO thread_ownership ON CONFLICT DO NOTHING`；访问前 `SELECT user_id FROM thread_ownership WHERE thread_id=$1` 验证归属 |
| `routers/artifacts.py` | 读取前 `SELECT user_id FROM thread_ownership` 验证归属 |
| `routers/secrets.py` | 新增：用户 key 管理 CRUD |

---

### Step 9：LangGraph 配置（`backend/langgraph.json`）

```json
{
  "auth": {
    "path": "src.auth.langgraph_handler:auth"
  },
  "graphs": {
    "lead_agent": "src.agents:make_lead_agent"
  }
}
```

---

### Step 10：Nginx 确认 Authorization Header 透传

检查 `docker/nginx/nginx.conf`，确保：
```nginx
location /api/langgraph/ {
    proxy_pass http://langgraph:2024/;
    proxy_set_header Authorization $http_authorization;  # 必须透传
}
location /api/ {
    proxy_pass http://gateway:8001/;
    proxy_set_header Authorization $http_authorization;  # 必须透传
}
```

---

### Step 11：Sandbox Skills 挂载策略（provisioner）

> **背景**：Sandbox Pod 与 Gateway/LangGraph 容器是独立进程，用户私有 skills 文件（存于 `.deer-flow/users/{id}/skills/custom/`）在 sandbox Pod 内不可见。

**为什么不能用容器自身文件系统或 HostPath**

| 方案 | 问题 |
|------|------|
| 容器 ephemeral 文件系统 | 容器重启丢失；多实例写入不同步；sandbox Pod 没有这些文件 |
| HostPath 挂载 | 只在单节点有效；多节点 K8s 下 Pod 可能被调度到没有该文件的节点 |
| **共享 PVC 挂载（采用）** | 与 Gateway/LangGraph 使用同一个网络存储卷，任何节点均可访问 |

**正确方案：Sandbox Pod 挂载同一个 PVC**

Provisioner 在创建 sandbox Pod 时，挂载与 Gateway/LangGraph 相同的 `deer_flow_data` PVC：

```python
# docker/provisioner/provisioner.py（修改 _build_pod_spec）
def _build_pod_spec(self, thread_id: str, user_id: str | None = None) -> dict:
    volumes = [
        # 共享数据卷（与 gateway/langgraph 相同的 PVC）
        {
            "name": "deer-flow-data",
            "persistentVolumeClaim": {"claimName": "deer-flow-data", "readOnly": True}
        },
    ]
    volume_mounts = [
        # 只挂载 skills 子目录（只读，限制 sandbox 访问范围）
        {
            "name": "deer-flow-data",
            "mountPath": "/app/skills/public",
            "subPath": "skills/public",
            "readOnly": True
        },
        *([{
            "name": "deer-flow-data",
            "mountPath": "/app/skills/custom",
            "subPath": f"users/{user_id}/skills/custom",
            "readOnly": True
        }] if user_id else []),
    ]
    ...
```

**Sandbox 内目录结构**：
```
/app/skills/
├── public/     ← 全局公共 skills（只读，来自 PVC skills/public/）
└── custom/     ← 当前用户私有 skills（只读，来自 PVC users/{id}/skills/custom/）
```

**SandboxMiddleware 传递 user_id 给 provisioner**：

```python
class SandboxMiddleware(AgentMiddleware):
    def __init__(self, lazy_init=True, user_id=None):
        self._user_id = user_id

    def _acquire_sandbox(self, thread_id: str) -> str:
        user_env = load_user_secrets(self._user_id)
        provider = get_sandbox_provider()
        return provider.acquire(thread_id, user_id=self._user_id, extra_env=user_env)
```

**Provisioner API 新增 `user_id` 参数**（`POST /sandboxes`）：
```json
{"thread_id": "xxx", "user_id": "user_abc"}
```

**本地开发（Docker Desktop / OrbStack）**：

PVC 实际上是宿主机目录的 bind mount，`subPath` 仍然有效。`docker-compose-prod.yaml` 中 `deer_flow_data` volume 使用 `bind mount` 到宿主机路径，provisioner 读取同一个卷，行为一致。

**注意事项**：
- PVC 必须支持 `ReadOnlyMany` 或 `ReadWriteMany`（NFS、EFS、Ceph 等），不能用 `ReadWriteOnce`
- 用户 skills 子目录不存在时忽略该 volumeMount（provisioner 预检查，避免 Pod 因 subPath 不存在而挂载失败）

---

### Step 12：依赖（`backend/pyproject.toml`）

新增：
- `"PyJWT>=2.8.0"`
- `"cryptography>=42.0.0"`（Fernet 加密）
- `"asyncpg>=0.29.0"` 或 `"psycopg[asyncio]>=3.2.0"`（PostgreSQL 异步驱动）
- `"langgraph-checkpoint-postgres>=2.0.0"`（替换 `langgraph-cli[inmem]`）

> `langgraph-cli[inmem]` 中 `[inmem]` extra 仅用于开发/测试；生产必须换 checkpoint-postgres。

---

## 现有代码冲突分析

> 本节描述当前代码与方案目标之间的具体差距，供实施时参考。
> **代码目前未做任何修改**，所有冲突均为"尚未实现"。

### 短期记忆（MemoryUpdateQueue）

**文件**：`backend/src/agents/memory/queue.py`

| 位置 | 当前状态 | 方案要求 |
|------|---------|---------|
| `ConversationContext` dataclass | `{thread_id, messages, timestamp, agent_name}`，无 `user_id` | 新增 `user_id: str \| None = None` 字段 |
| `add()` 方法签名 | `add(thread_id, messages, agent_name=None)` | 新增 `user_id=None` 参数并透传至 `ConversationContext` |

---

### 长期记忆（MemoryUpdater）

**文件**：`backend/src/agents/memory/updater.py`

当前实现：
- 存储：`memory.json` 文件（路径由 `MemoryConfig.storage_path` 配置，默认 `.deer-flow/memory.json`）
- 缓存：`_memory_cache: dict[str|None, tuple[dict, float|None]]`，key 为 `agent_name`，value 为 `(data, file_mtime)`
- 缓存失效：比对 `stat().st_mtime`，文件变更时刷新
- Per-agent：不同 `agent_name` 对应不同 JSON 文件（`agent_memory_file(agent_name)`）
- 原子写：先写 `.tmp` 再 `rename`

| 位置 | 当前状态 | 方案要求 |
|------|---------|---------|
| `get_memory_data()` | 读文件，参数 `(agent_name=None)` | 查 PostgreSQL `user_memory` 表，加 `user_id=None` 参数 |
| `MemoryUpdater.update_memory()` | 写文件，无 `user_id` | upsert 到 `user_memory` 表，加 `user_id=None` 参数 |
| `_memory_cache` key | `agent_name: str \| None` | 改为 `(user_id, agent_name): tuple` |
| 缓存失效机制 | 比对 `file_mtime` | 改为纯 TTL（PostgreSQL 无 mtime，用 `time.time()` 比对缓存写入时间） |
| `_get_memory_file_path()` | 返回文件路径 | 整个函数删除，改为 `db.get_memory()` 调用 |
| 原子写 `.tmp` → rename | 文件原子替换 | 删除，PostgreSQL 事务保证原子性 |
| `MemoryConfig.storage_path` | 控制文件路径 | 此配置变为无效（可保留供 `POSTGRES_URI` 未配置时的开发 fallback） |

**兼容项（不需要改动）**：
- 内存数据结构 `{user, history, facts}` 完全兼容 PostgreSQL `JSONB` 列，原样存入
- Per-agent 隔离逻辑：原来靠不同文件，改后靠 `agent_name` 列，语义等价

---

### Memory 中间件

**文件**：`backend/src/agents/middlewares/memory_middleware.py`

| 位置 | 当前状态 | 方案要求 |
|------|---------|---------|
| `__init__` 签名 | `(self, agent_name=None)` | 新增 `user_id=None`，保存为 `self._user_id` |
| `queue.add()` 调用 | 无 `user_id` 参数 | 加入 `user_id=self._user_id` |

---

### Lead Agent

**文件**：`backend/src/agents/lead_agent/agent.py`

| 位置 | 当前状态 | 方案要求 |
|------|---------|---------|
| `make_lead_agent(config)` | 不提取 `user_id` | 从 `config.get("metadata", {}).get("owner")` 提取 `user_id` |
| `_build_middlewares()` 调用 | `MemoryMiddleware(agent_name)` | `MemoryMiddleware(agent_name, user_id=user_id)` |
| `_get_memory_context()` 调用 | `get_memory_data(agent_name)` | `get_memory_data(agent_name, user_id=user_id)` |

---

### Gateway Memory 路由

**文件**：`backend/src/gateway/routers/memory.py`

| 位置 | 当前状态 | 方案要求 |
|------|---------|---------|
| `GET /api/memory` | `get_memory_data(agent_name)` | 加 `user_id: str = Depends(get_current_user_id)` 并传入 `get_memory_data()` |
| `POST /api/memory/reload` | 刷新文件缓存 | 刷新 `(user_id, agent_name)` 对应的 DB 缓存 |

---

### 不涉及现有代码冲突的新增文件

以下为方案要求新建的文件，当前不存在，需从头实现：

| 文件 | 说明 |
|------|------|
| `backend/src/agents/memory/db.py` | PostgreSQL `user_memory` 表 CRUD（`get_memory` / `save_memory`） |
| `backend/src/auth/__init__.py` | `get_current_user_id` FastAPI dependency |
| `backend/src/auth/jwt_utils.py` | JWT 验证逻辑 |
| `backend/src/auth/gateway_middleware.py` | Gateway 认证中间件 |
| `backend/src/auth/langgraph_handler.py` | LangGraph auth handler |
| `backend/src/auth/secrets.py` | 用户 secrets Fernet 加解密 |
| `backend/src/auth/rate_limit.py` | Redis per-user 限流 |
| `backend/src/gateway/routers/secrets.py` | 用户 key CRUD API |

---

## 关键文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `backend/src/auth/__init__.py` | 新建 | FastAPI dependency 导出 |
| `backend/src/auth/jwt_utils.py` | 新建 | JWT 验证，user_id 提取 |
| `backend/src/auth/gateway_middleware.py` | 新建 | FastAPI 认证中间件（含限流调用） |
| `backend/src/auth/langgraph_handler.py` | 新建 | LangGraph Platform auth handler |
| `backend/src/auth/secrets.py` | 新建 | 用户 secrets 加解密，key 解析 |
| `backend/src/auth/rate_limit.py` | 新建 | per-user Redis 限流 |
| `backend/src/config/paths.py` | 修改（追加） | user_* 文件路径方法，secrets 路径（无 memory/owner 文件） |
| `backend/src/config/agents_config.py` | 修改 | 所有函数加 user_id 参数 |
| `backend/src/config/tool_config.py` | 修改 | 工具定义新增 `key_env_var` 字段 |
| `backend/src/agents/memory/db.py` | 新建 | PostgreSQL memory CRUD（`user_memory` 表） |
| `backend/src/agents/memory/updater.py` | 修改 | user_id 参数，改调 db.py（移除文件路径逻辑） |
| `backend/src/agents/memory/queue.py` | 修改 | user_id 穿透 |
| `backend/src/agents/middlewares/memory_middleware.py` | 修改 | user_id 构造参数 |
| `backend/src/agents/middlewares/sandbox_middleware.py` | 修改 | user_id 构造参数，sandbox env 注入 |
| `backend/src/agents/lead_agent/agent.py` | 修改 | 提取 user_id，透传给 middlewares 和 tools |
| `backend/src/skills/loader.py` | 修改 | user_id 参数，用户私有 skills |
| `backend/src/tools/tools.py` | 修改 | user_id 参数，per-user 工具实例化和缓存 |
| `backend/src/mcp/cache.py` | 修改 | 全局缓存 → per-user dict 缓存 |
| `backend/src/gateway/app.py` | 修改 | 注册 AuthMiddleware |
| `backend/src/gateway/routers/memory.py` | 修改 | user_id dependency |
| `backend/src/gateway/routers/agents.py` | 修改 | user_id dependency，用户 agents 目录 |
| `backend/src/gateway/routers/skills.py` | 修改 | user_id dependency，用户 skills 目录 |
| `backend/src/gateway/routers/uploads.py` | 修改 | thread_ownership 表写/验（PostgreSQL） |
| `backend/src/gateway/routers/artifacts.py` | 修改 | thread_ownership 表验证 |
| `backend/src/gateway/routers/secrets.py` | 新建 | 用户 key CRUD API |
| `backend/src/community/aio_sandbox/redis_state_store.py` | 新建 | 补全已有 TODO，多节点 sandbox 状态 |
| `backend/langgraph.json` | 修改 | 添加 auth + store（PostgreSQL checkpoint） |
| `backend/pyproject.toml` | 修改 | 添加 PyJWT、cryptography、asyncpg、langgraph-checkpoint-postgres |
| `docker/nginx/nginx.conf` | 修改 | 确保 Authorization header 透传 |
| `docker/provisioner/provisioner.py` | 修改 | `_build_pod_spec` 支持 user_id 动态挂载用户 skills |
| `docker/docker-compose-prod.yaml` | 新建 | 生产多实例配置（含 PostgreSQL、Redis） |

---

## 高并发与水平扩展

### 问题分析

| 组件 | 问题 | 解决方案 |
|------|------|--------|
| **LangGraph `inmem`** | Thread 对话状态存进程内存，多实例后同一 thread 打到不同实例 → 状态丢失 | ✅ PostgreSQL checkpoint |
| **`memory.json` 多实例写** | 各实例独立缓存 + NFS 锁不可靠 → 切换实例会导致记忆读到旧数据 | ✅ PostgreSQL `user_memory` 表 |
| **Thread 归属（`.owner` 文件）** | 多实例并发首次写可能重复；NFS 原子性不保证 | ✅ PostgreSQL `thread_ownership` 表 |
| **`FileSandboxStateStore`** | 已用 `fcntl.flock`，单节点安全；多节点需 Redis | Phase 2 → `RedisSandboxStateStore` |
| **JWT 验证** | 无状态，天然支持水平扩展 | ✓ 无需处理 |
| **per-user 工具/MCP 缓存** | 进程级缓存，各实例独立 — 内存换速度，可接受 | ✓ 无需处理 |

### PostgreSQL 表结构

```sql
-- LangGraph 对话状态（由 langgraph-checkpoint-postgres 自动建表）
-- langgraph_checkpoints, langgraph_writes, langgraph_migrations ...

-- 用户长期记忆（替代 memory.json）
CREATE TABLE user_memory (
    user_id    TEXT        NOT NULL,
    agent_name TEXT        NOT NULL DEFAULT '',  -- '' = 通用记忆，否则为 agent 名
    data       JSONB       NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, agent_name)
);

-- Thread 归属（替代 .owner 文件）
CREATE TABLE thread_ownership (
    thread_id  TEXT        PRIMARY KEY,
    user_id    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON thread_ownership (user_id);
```

### 扩展架构

```
                    ┌─────────────────────────┐
                    │      Nginx LB :2026      │
                    │  least_conn 轮询          │
                    └────────────┬────────────┘
              ┌──────────────────┴─────────────────────┐
      ┌───────▼──────┐                        ┌────────▼─────┐
      │  Gateway ×N  │                        │ LangGraph ×N │
      │  :8001       │                        │  :2024       │
      └───────┬──────┘                        └────────┬─────┘
              │                                        │
   ┌──────────▼────────────────────────────────────────▼────────┐
   │                       PostgreSQL                            │
   │  ├── langgraph_checkpoints   (Thread 对话状态，无状态路由)    │
   │  ├── user_memory             (用户长期记忆，原 memory.json)   │
   │  └── thread_ownership        (Thread 归属，原 .owner 文件)   │
   └─────────────────────────────────────────────────────────────┘
              │
   ┌──────────▼──────────┐    ┌─────────────────────────────────┐
   │        Redis         │    │      Shared Volume (PVC)        │
   │  └── rate_limit only │    │  ├── users/{id}/               │
   └─────────────────────┘    │  │   ├── secrets.enc            │
                               │  │   ├── skills/custom/         │
                               │  │   ├── agents/               │
                               │  │   └── extensions_config.json│
                               │  ├── threads/{id}/user-data/   │
                               │  └── skills/public/            │
                               └─────────────────────────────────┘
```

### Phase 1：PostgreSQL 接管（必须优先完成）

**1.1 LangGraph 切换 PostgreSQL checkpoint**

```json
// backend/langgraph.json
{
  "auth": {"path": "src.auth.langgraph_handler:auth"},
  "graphs": {"lead_agent": "src.agents:make_lead_agent"},
  "store": {
    "uri": "${POSTGRES_URI}",
    "table_prefix": "langgraph_"
  }
}
```

效果：Thread 对话状态持久化 → 任意 LangGraph 实例均可接续任意 thread，**无需 sticky session**。

**1.2 `user_memory` 表替代 `memory.json`**

内存更新直接 upsert 到 PostgreSQL（见 Step 3），无需分布式锁、无文件竞争：

```python
# 每个实例各自写，PostgreSQL MVCC 保证一致性
await db.execute("""
    INSERT INTO user_memory (user_id, agent_name, data, updated_at)
    VALUES ($1, $2, $3, NOW())
    ON CONFLICT (user_id, agent_name) DO UPDATE
    SET data = EXCLUDED.data, updated_at = NOW()
""", user_id, agent_name, json.dumps(data))
```

进程内 TTL 缓存保留（加速读），缓存 key 为 `(user_id, agent_name)`，过期时回查 DB。

**1.3 `thread_ownership` 表替代 `.owner` 文件**

```python
# 首次上传时记录归属（ON CONFLICT DO NOTHING 保证幂等）
await db.execute("""
    INSERT INTO thread_ownership (thread_id, user_id)
    VALUES ($1, $2)
    ON CONFLICT DO NOTHING
""", thread_id, user_id)

# 访问时验证归属
row = await db.fetchrow(
    "SELECT user_id FROM thread_ownership WHERE thread_id=$1", thread_id
)
if row and row["user_id"] != user_id:
    raise HTTPException(403, "Access denied")
```

**1.4 per-user Redis 限流**

```python
# backend/src/auth/rate_limit.py
async def check_rate_limit(user_id: str) -> None:
    window = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    limit = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    key = f"rl:{user_id}:{int(time.time() // window)}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window)
    if count > limit:
        raise HTTPException(429, "Rate limit exceeded")
```

在 `AuthMiddleware` 中验证 JWT 成功后调用。

### Phase 2：完整水平扩展（多节点）

**2.1 `RedisSandboxStateStore`（补全已有 TODO）**

`state_store.py:22` 已注明 `TODO: RedisSandboxStateStore`，多节点时替换 `FileSandboxStateStore`：

```python
# backend/src/community/aio_sandbox/redis_state_store.py
class RedisSandboxStateStore(SandboxStateStore):
    def save(self, thread_id, info):
        self.redis.setex(f"sandbox:{thread_id}", self.ttl, json.dumps(info.to_dict()))

    @contextmanager
    def lock(self, thread_id):
        with self.redis.lock(f"sandbox_lock:{thread_id}", timeout=30, blocking_timeout=10):
            yield
```

### 生产 Docker Compose

```yaml
# docker/docker-compose-prod.yaml（新建）
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: deerflow
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d deerflow"]

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data

  gateway:
    deploy:
      replicas: 2
    environment:
      POSTGRES_URI: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/deerflow
      REDIS_URI: redis://redis:6379
      SECRETS_MASTER_KEY: ${SECRETS_MASTER_KEY}
      AUTH_ENABLED: "true"
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    volumes:
      - deer_flow_data:/app/.deer-flow

  langgraph:
    deploy:
      replicas: 2
    environment:
      POSTGRES_URI: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/deerflow
      AUTH_ENABLED: "true"
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    volumes:
      - deer_flow_data:/app/.deer-flow

volumes:
  postgres_data:
  redis_data:
  deer_flow_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/deer-flow

networks:
  deer-flow:
    driver: bridge
```

**Nginx 多实例 LB**（`docker/nginx/nginx.prod.conf`）：
```nginx
upstream gateway_pool {
    least_conn;
    server gateway_1:8001;
    server gateway_2:8001;
}
upstream langgraph_pool {
    least_conn;  # PostgreSQL checkpoint 后无需 sticky session
    server langgraph_1:2024;
    server langgraph_2:2024;
}
```

### 扩展环境变量

```env
# PostgreSQL（Session + Memory + Thread 归属，统一存储）
POSTGRES_URI=postgresql://deerflow:pass@postgres:5432/deerflow
POSTGRES_USER=deerflow
POSTGRES_PASSWORD=...

# Redis（仅用于限流）
REDIS_URI=redis://redis:6379
RATE_LIMIT_REQUESTS=100     # 每用户每分钟最大请求数
RATE_LIMIT_WINDOW=60        # 统计窗口（秒）
```

---

## 向后兼容保证

- `AUTH_ENABLED=false`（默认）：所有请求 `user_id = "default"`，行为与之前完全一致
- 所有新增 `user_id` 参数均有默认值 `None`，`None` 时回退原有全局路径/逻辑
- `thread_ownership` 表中 thread_id 不存在时视为无归属限制（兼容旧数据）
- `SECRETS_MASTER_KEY` 未配置时，`load_user_secrets` 返回空 dict，工具降级用平台 key
- `POSTGRES_URI` 未配置时，LangGraph 保持 `inmem`，`user_memory` 降级写本地文件（开发模式）
- `REDIS_URI` 未配置时，跳过限流（开发模式）

---

## 验证方案

1. **`AUTH_ENABLED=false`（默认）**：现有功能全部正常，数据写入 `users/default/`
2. **`AUTH_ENABLED=true`**：
   - 无 token 请求 → 401；无效 token → 401
   - 有效 JWT（user_id=A）：memory、agents、skills 全部写入 `users/A/`
   - 另一用户（user_id=B）：无法访问 A 的 thread uploads/artifacts → 403
   - 两用户各自安装 skill → 各自 `users/{id}/skills/custom/` 独立
   - 两用户各自对话 → `user_memory` 表中各自行独立，互不干扰
   - LangGraph 线程列表 → 各用户只能看到自己的线程
3. **Key 隔离验证**：
   - 用户 A 配置自己的 `TAVILY_API_KEY` → tools 使用 A 的 key，sandbox env 也是
   - 用户 B 未配置 → tools 降级使用平台 key
   - 直接读 `users/A/secrets.enc` → 密文，无 `SECRETS_MASTER_KEY` 不可解
4. **水平扩展验证**：
   - 启动 2 个 LangGraph 实例，连续对话同一 thread → 两实例均能正确接续（PostgreSQL checkpoint）
   - 并发 100 个用户同时对话 → `user_memory` 无数据竞争（PostgreSQL MVCC + upsert）
   - 两实例交替处理同一用户请求 → 记忆一致（均读写同一 PostgreSQL 记录）
   - 重启 1 个实例 → 未完成的对话无影响（checkpoint 持久化）
   - Rate limit：同一用户超过阈值 → 429，其他用户不受影响

---

## 备份策略

### 数据分层

| 数据 | 存储 | 备份方式 | 恢复粒度 |
|------|------|---------|---------|
| 对话状态 + 记忆 + 归属 | PostgreSQL | 见下 | 行级 / PITR |
| Skills / Agents / Secrets | 共享 PVC（NFS/EFS） | 见下 | 文件级快照 |
| 上传文件 / 输出文件 | 共享 PVC（NFS/EFS） | 同上 | 文件级快照 |

### PostgreSQL 备份

**自建 PostgreSQL（docker-compose-prod.yaml）**：

```bash
# 定期逻辑备份（每日 cron）
pg_dump -h postgres -U deerflow deerflow | gzip > backup_$(date +%Y%m%d).sql.gz

# 仅备份关键业务表（更轻量）
pg_dump -h postgres -U deerflow deerflow \
  -t user_memory -t thread_ownership \
  | gzip > memory_backup_$(date +%Y%m%d).sql.gz

# 恢复
gunzip -c backup_20260301.sql.gz | psql -h postgres -U deerflow deerflow
```

**托管数据库（推荐生产使用）**：

| 服务 | 备份方式 | PITR |
|------|---------|------|
| AWS RDS / Aurora | 自动每日快照 + 5 分钟 WAL | ✅ |
| Supabase | 自动每日备份（Pro 计划）| ✅ |
| Google Cloud SQL | 自动备份 + 实时 WAL | ✅ |
| 阿里云 RDS | 自动备份 | ✅ |

> 托管数据库开箱即用备份，无需额外配置，**生产环境强烈推荐**。

### 共享 PVC 备份（Skills / Agents / Secrets / Uploads）

**什么情况会丢失**：
- `hostPath` 单节点挂载：节点磁盘损坏丢失，或 Pod 被调度到其他节点时"看不见"
- 正确配置（NFS/EFS）：**不会丢失**，除非手动删除或存储服务故障

**备份方案**：

```bash
# 方案 A：rsync 定期同步到另一台机器或对象存储
rsync -avz /data/deer-flow/ user@backup-server:/backup/deer-flow/

# 方案 B：AWS EFS → AWS Backup（托管，自动保留策略）
# 在 AWS Console → Backup → 创建 backup plan → 选 EFS 资源

# 方案 C：对象存储同步（MinIO / S3）
mc mirror /data/deer-flow s3/deer-flow-backup
```

**最小备份优先级**：

```
🔴 必须备份：users/{id}/secrets.enc（用户加密 key，丢失无法恢复）
🟡 建议备份：users/{id}/agents/、users/{id}/skills/custom/（用户配置）
🟢 可重建：skills/public/（代码仓库里有，重新部署即可）
🟢 可重建：threads/{id}/user-data/outputs/（输出可重新生成，uploads 按需决定）
```

### 总结

- **单节点开发**：PostgreSQL + 本地目录，手动 `pg_dump` 即可
- **生产多节点**：托管 PostgreSQL（RDS/Supabase）+ AWS EFS（含 AWS Backup），几乎零运维备份成本
