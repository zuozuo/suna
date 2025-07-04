# MCP（Model Context Protocol）集成完整指南

## 概述

MCP（Model Context Protocol）是 Suna 项目中用于集成外部工具和服务的核心协议。通过 MCP，Suna 可以动态地连接和使用各种第三方服务，大大扩展了 Agent 的能力边界。本文档全面介绍 MCP 在 Suna 中的使用、凭证管理和安全机制。

## MCP 的集成架构

### 1. 核心组件

#### MCPManager (`backend/mcp_local/client.py`)
- **职责**：管理 MCP 服务器连接的核心类
- **功能**：
  - 连接到 Smithery 托管的 MCP 服务器
  - 将 MCP 工具转换为 OpenAPI 格式供 LLM 使用
  - 执行 MCP 工具调用并处理响应
- **连接方式**：通过 HTTP Streamable 协议连接到 Smithery 服务器

#### MCPToolWrapper (`backend/agent/tools/mcp_tool_wrapper.py`)
- **职责**：将 MCP 工具包装成 AgentPress 工具
- **功能**：
  - 动态创建每个 MCP 工具的独立方法
  - 支持标准 MCP（Smithery）和自定义 MCP 服务器
  - 处理 SSE、HTTP 和 STDIO 三种连接方式
  - 生成符合 OpenAPI 规范的工具描述

### 2. MCP 服务类型

#### 标准 MCP 服务（通过 Smithery）
- **特点**：由 Smithery 平台托管和管理
- **优势**：稳定、易用、无需自己部署
- **示例**：
  ```python
  {
      "name": "Exa Search",
      "qualifiedName": "exa",
      "config": {"exaApiKey": "xxx"},
      "enabledTools": ["web_search_exa"]
  }
  ```

#### 自定义 MCP 服务
支持三种连接方式：

1. **SSE (Server-Sent Events)**
   ```python
   {
       "name": "Custom SSE Server",
       "customType": "sse",
       "config": {
           "url": "https://example.com/mcp/sse",
           "headers": {"Authorization": "Bearer xxx"}
       }
   }
   ```

2. **HTTP (Streamable HTTP)**
   ```python
   {
       "name": "Custom HTTP Server",
       "customType": "http",
       "config": {
           "url": "https://example.com/mcp/http"
       }
   }
   ```

3. **STDIO (JSON-RPC over stdio)**
   ```python
   {
       "name": "Local MCP Server",
       "customType": "json",
       "config": {
           "command": "npx",
           "args": ["@modelcontextprotocol/server-playwright"],
           "env": {"DISPLAY": ":1"}
       }
   }
   ```

## 为什么需要 MCP 凭证管理

### 1. 核心作用

通过 MCP，Suna 的 Agent 可以：
- 无需修改核心代码即可集成新服务
- 根据任务需求动态加载所需工具
- 实现与数十种第三方服务的集成

### 2. 多样化的服务集成

Suna 通过 MCP 集成了大量第三方服务：

- **开发工具**：GitHub、GitLab、Bitbucket（代码管理）
- **项目管理**：Linear、Jira、Notion、Asana（任务跟踪）
- **AI 搜索**：Exa、Perplexity、DuckDuckGo（信息检索）
- **通信协作**：Slack、Discord、Teams（团队沟通）
- **自动化测试**：Playwright、Puppeteer（Web 自动化）
- **数据库访问**：PostgreSQL、MySQL、MongoDB（数据操作）

### 3. 安全性要求

每个 MCP 服务都需要相应的认证凭证：

```json
{
  "github": {"token": "ghp_xxxxxxxxxxxx"},
  "linear": {"api_key": "lin_api_xxxxxxxxxxxx"},
  "openai": {"api_key": "sk-xxxxxxxxxxxx"},
  "slack": {"token": "xoxb-xxxxxxxxxxxx"}
}
```

**安全挑战**：
- 这些凭证包含敏感的 API 密钥和访问令牌
- 如果泄露，可能导致严重的安全问题
- 需要防止凭证在日志、错误信息中意外暴露

## MCP 凭证安全管理系统

### 核心特性

1. **Fernet 对称加密存储**：使用 cryptography 库的 Fernet 加密算法
2. **多配置文件支持**：允许为同一服务创建多个凭证配置
3. **凭证使用审计**：详细记录所有凭证访问和使用情况
4. **完整性校验**：通过 SHA256 哈希确保数据未被篡改
5. **访问控制**：基于用户 ID 的严格访问控制

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                             │
│  (secure_api.py - RESTful endpoints for credential mgmt)    │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│                   Credential Manager                         │
│  (credential_manager.py - Core encryption/decryption logic) │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│                    Database Layer                            │
│  (PostgreSQL - Encrypted credential storage)                 │
└─────────────────────────────────────────────────────────────┘
```

### Fernet 对称加密实现

#### 加密过程

```python
def _encrypt_config(self, config: Dict[str, Any]) -> str:
    """加密配置字典"""
    # 序列化配置为 JSON
    config_bytes = json.dumps(config).encode()
    
    # 计算原始数据的 SHA256 哈希（用于完整性校验）
    hash_value = hashlib.sha256(config_bytes).hexdigest()
    
    # 将哈希值添加到数据中
    data_with_hash = json.dumps({
        "config": config,
        "hash": hash_value
    }).encode()
    
    # 使用 Fernet 加密
    encrypted = self.cipher_suite.encrypt(data_with_hash)
    
    # 返回 Base64 编码的加密数据
    return base64.b64encode(encrypted).decode()
```

#### 解密过程

```python
def _decrypt_config(self, encrypted_config: str) -> Dict[str, Any]:
    """解密配置字符串"""
    try:
        # Base64 解码
        encrypted_bytes = base64.b64decode(encrypted_config.encode())
        
        # Fernet 解密
        decrypted = self.cipher_suite.decrypt(encrypted_bytes)
        
        # 解析 JSON
        data = json.loads(decrypted.decode())
        config = data["config"]
        stored_hash = data["hash"]
        
        # 验证完整性
        config_bytes = json.dumps(config).encode()
        calculated_hash = hashlib.sha256(config_bytes).hexdigest()
        
        if calculated_hash != stored_hash:
            raise ValueError("Config integrity check failed")
        
        return config
    except Exception as e:
        logger.error(f"Failed to decrypt config: {e}")
        raise ValueError(f"Failed to decrypt config: {e}")
```

### 多配置文件支持

系统支持为同一个 MCP 服务创建多个命名的凭证配置文件，适用于多账号场景。

```python
class CredentialProfile:
    """凭证配置文件模型"""
    id: str
    user_id: str
    mcp_qualified_name: str
    profile_name: str
    display_name: str
    encrypted_config: str
    is_default: bool
    created_at: datetime
    updated_at: datetime
```

**使用场景**：
- **多账号管理**：用户可以为 GitHub MCP 创建多个配置文件，分别对应个人账号和工作账号
- **环境切换**：开发、测试、生产环境使用不同的凭证配置
- **权限分离**：不同的配置文件可以有不同的权限范围

### 凭证使用审计

#### 审计日志数据模型

```sql
CREATE TABLE credential_usage_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credential_id UUID NOT NULL,
    user_id TEXT NOT NULL,
    instance_id TEXT,
    operation_type TEXT NOT NULL,  -- 'test_connection', 'tool_call', etc.
    success BOOLEAN NOT NULL,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 审计日志示例

```json
{
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "credential_id": "456e7890-e89b-12d3-a456-426614174000",
    "user_id": "user_123",
    "instance_id": "instance_456",
    "operation_type": "tool_call",
    "success": true,
    "error_message": null,
    "metadata": {
        "tool_name": "github_create_issue",
        "arguments": {
            "repo": "myorg/myrepo",
            "title": "New feature request"
        },
        "duration_ms": 1234
    },
    "created_at": "2024-01-01T10:00:00Z"
}
```

## 使用场景

### 1. 在 Agent 系统中的应用

#### 工具注册流程
1. Agent 配置中包含 `configured_mcps` 和 `custom_mcps`
2. 启动 Agent 时，MCPToolWrapper 被初始化
3. 连接到所有配置的 MCP 服务器
4. 动态生成每个 MCP 工具的方法
5. 注册到 AgentPress 的工具注册表

#### 工具调用流程
1. LLM 通过函数调用请求使用 MCP 工具
2. MCPToolWrapper 接收调用请求
3. 根据工具名称路由到对应的 MCP 服务器
4. 执行工具调用并返回结果

### 2. 在 Workflow 系统中的应用

工作流系统支持 `MCP_TOOL` 类型的节点，可以在工作流中直接使用 MCP 工具：

```python
{
    "type": "MCP_TOOL",
    "config": {
        "tool_name": "mcp_exa_web_search_exa",
        "arguments": {
            "query": "latest AI developments",
            "num_results": 10
        }
    }
}
```

## 实际应用案例

### 案例 1：DevOps 自动化

```python
# DevOps Agent 需要多个服务的凭证
devops_agent = Agent(
    name="DevOps Assistant",
    mcp_tools=[
        {"server": "github", "profile": "default"},      # 代码管理
        {"server": "aws", "profile": "production"},      # 云服务
        {"server": "slack", "profile": "team"},          # 通知
        {"server": "datadog", "profile": "monitoring"}   # 监控
    ]
)
```

### 案例 2：数据分析工作流

```python
# 数据分析 Agent 需要数据库和 API 凭证
data_agent = Agent(
    name="Data Analyst",
    mcp_tools=[
        {"server": "postgresql", "profile": "analytics_db"},
        {"server": "bigquery", "profile": "warehouse"},
        {"server": "openai", "profile": "gpt4"},
        {"server": "slack", "profile": "reports_channel"}
    ]
)
```

### 案例 3：客户支持自动化

```python
# 客户支持 Agent 需要多个沟通渠道的凭证
support_agent = Agent(
    name="Customer Support",
    mcp_tools=[
        {"server": "zendesk", "profile": "support"},
        {"server": "slack", "profile": "customer_success"},
        {"server": "gmail", "profile": "support_email"},
        {"server": "stripe", "profile": "billing_readonly"}
    ]
)
```

## API 端点

### 凭证管理端点

1. **存储凭证**：
   ```
   POST /api/mcp/credentials
   Content-Type: application/json
   
   {
       "mcp_qualified_name": "github@1.0.0",
       "display_name": "GitHub Personal",
       "config": {
           "token": "ghp_xxxxxxxxxxxx"
       }
   }
   ```

2. **获取凭证列表**：
   ```
   GET /api/mcp/credentials
   
   响应：
   [
       {
           "id": "123e4567-e89b-12d3-a456-426614174000",
           "mcp_qualified_name": "github@1.0.0",
           "display_name": "GitHub Personal",
           "last_used_at": "2024-01-01T10:00:00Z",
           "created_at": "2024-01-01T09:00:00Z"
       }
   ]
   ```

3. **测试凭证**：
   ```
   POST /api/mcp/credentials/{mcp_qualified_name}/test
   
   响应：
   {
       "success": true,
       "message": "Connection test successful"
   }
   ```

## 关键实现细节

### 1. 动态方法生成
MCPToolWrapper 为每个 MCP 工具动态创建独立的方法：
```python
def _create_dynamic_method(self, tool_name: str, tool_info: Dict[str, Any]):
    async def dynamic_tool_method(**kwargs) -> ToolResult:
        return await self._execute_mcp_tool(tool_name, kwargs)
    
    dynamic_tool_method.__name__ = method_name
    setattr(self, method_name, dynamic_tool_method)
```

### 2. Schema 转换
将 MCP 工具的输入 schema 转换为 OpenAPI 格式：
```python
openapi_function_schema = {
    "type": "function",
    "function": {
        "name": method_name,
        "description": full_description,
        "parameters": tool_info.get("parameters", {})
    }
}
```

### 3. 连接管理
- 使用连接池管理多个 MCP 服务器
- 支持超时和重试机制
- 优雅的错误处理和降级

## 安全最佳实践

### 1. 密钥管理
- **环境变量隔离**：加密密钥通过环境变量 `MCP_CREDENTIAL_ENCRYPTION_KEY` 传入，不硬编码在代码中
- **密钥轮换**：定期更新加密密钥，并提供密钥迁移工具
- **密钥强度**：使用 Fernet.generate_key() 生成的 32 字节密钥（256 位）

### 2. 访问控制
- **用户隔离**：每个用户只能访问自己的凭证
- **最小权限原则**：API 端点返回凭证列表时不包含敏感配置数据
- **会话管理**：通过 JWT 或类似机制进行身份验证

### 3. 传输安全
- **HTTPS 强制**：所有 API 通信必须使用 HTTPS
- **请求验证**：验证请求来源和完整性
- **响应过滤**：确保敏感数据不会意外泄露在响应中

### 4. 审计和监控
- **全面日志**：记录所有凭证访问和使用情况
- **异常检测**：监控异常的访问模式
- **定期审查**：定期检查审计日志，识别潜在的安全问题

### 5. 错误处理
- **安全的错误消息**：避免在错误消息中泄露敏感信息
- **失败安全**：解密或验证失败时，默认拒绝访问
- **速率限制**：防止暴力破解攻击

## 性能优化

### 1. 缓存策略

```python
class CredentialCache:
    def __init__(self, ttl: int = 300):  # 5分钟缓存
        self._cache: Dict[str, Tuple[MCPCredential, float]] = {}
        self._ttl = ttl
    
    def get(self, key: str) -> Optional[MCPCredential]:
        if key in self._cache:
            credential, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return credential
            else:
                del self._cache[key]
        return None
```

### 2. 批量操作
- 支持批量获取凭证
- 批量更新最后使用时间
- 批量审计日志写入

### 3. 数据库优化
- 适当的索引策略
- 连接池管理
- 查询优化

## 最佳实践总结

1. **配置管理**
   - 敏感信息（如 API 密钥）应通过环境变量管理
   - 使用 `enabledTools` 精确控制可用工具

2. **性能优化**
   - 工具初始化是异步的，避免阻塞
   - 连接复用，减少建立连接的开销

3. **错误处理**
   - 所有工具调用都有超时保护
   - 失败时返回明确的错误信息

4. **安全性**
   - 验证工具输入参数
   - 限制工具执行权限
   - 审计工具调用日志

## 相关文档

- [工具系统总览](../03-tool-system/tool-system-overview.md) - 了解完整的工具系统
- [工作流引擎](./workflow-engine.md) - MCP 在工作流中的应用
- [Ask 工具流程](./ask-tool-backend-flow.md) - 特定工具的实现示例

## 总结

MCP 是 Suna 项目实现工具扩展性的核心机制。通过 MCP 和完善的凭证管理系统，Suna 可以：

1. **无缝集成**第三方服务，无需修改核心代码
2. **动态发现**和使用新工具
3. **统一管理**不同类型的工具接口
4. **灵活配置**每个 Agent 的工具集
5. **安全存储**和使用敏感凭证

这种设计使得 Suna 成为一个真正可扩展的 AI Agent 平台，能够适应各种不同的使用场景和需求，同时确保用户凭证的安全性。