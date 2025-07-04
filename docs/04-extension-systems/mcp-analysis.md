# Suna 项目中 MCP（Model Context Protocol）使用分析

## 概述

MCP（Model Context Protocol）是 Suna 项目中用于集成外部工具和服务的核心协议。通过 MCP，Suna 可以动态地连接和使用各种第三方服务，大大扩展了 Agent 的能力边界。

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

## 具体的 MCP 服务集成案例

### 1. 开发与版本控制
- **GitHub**：代码仓库管理、PR 操作、Issue 管理
- **GitLab**：GitLab 项目管理
- **Bitbucket**：Bitbucket 仓库操作

### 2. AI 与搜索
- **Exa**：高级网络搜索
- **Perplexity**：AI 驱动的搜索
- **DuckDuckGo**：隐私搜索引擎

### 3. 项目管理
- **Linear**：现代项目管理工具
- **Jira**：企业级项目管理
- **Notion**：知识库和项目管理
- **Asana**：任务和项目协作

### 4. 通信与协作
- **Slack**：团队沟通
- **Discord**：社区交流
- **Teams**：微软团队协作

### 5. 自动化与生产力
- **Playwright**：浏览器自动化
- **Puppeteer**：网页自动化
- **Desktop Commander**：桌面自动化

### 6. 数据与分析
- **PostgreSQL**：关系型数据库
- **MySQL**：关系型数据库
- **MongoDB**：NoSQL 数据库

## Tool System 架构设计

### 1. 工具抽象层
- **Tool 基类**：所有工具的基础接口
- **ToolRegistry**：工具注册和管理
- **ToolSchema**：工具的 OpenAPI/XML 描述

### 2. 工具类型
- **内置工具**：如 SandboxShellTool、SandboxFilesTool 等
- **MCP 工具**：通过 MCPToolWrapper 动态生成
- **自定义工具**：用户可以实现自己的工具类

### 3. 工具执行
- **同步/异步支持**：所有工具方法都是异步的
- **错误处理**：统一的 ToolResult 响应格式
- **权限控制**：基于 Agent 配置的工具启用/禁用

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

## 最佳实践

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

## 总结

MCP 是 Suna 项目实现工具扩展性的核心机制。通过 MCP，Suna 可以：

1. **无缝集成**第三方服务，无需修改核心代码
2. **动态发现**和使用新工具
3. **统一管理**不同类型的工具接口
4. **灵活配置**每个 Agent 的工具集

这种设计使得 Suna 成为一个真正可扩展的 AI Agent 平台，能够适应各种不同的使用场景和需求。