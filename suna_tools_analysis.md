# Suna 工具系统详细分析

## 工具系统架构概述

Suna 的工具系统基于 AgentPress 框架构建，采用了插件式的架构设计，支持 OpenAPI 和 XML 两种 schema 格式。

### 核心组件

1. **Tool 基类** (`agentpress/tool.py`)
   - 所有工具的抽象基类
   - 提供 schema 注册和结果处理功能
   - 支持装饰器模式定义工具方法

2. **ToolRegistry** (`agentpress/tool_registry.py`)
   - 工具注册中心
   - 管理所有已注册的工具实例
   - 提供工具查找和 schema 获取功能

3. **SandboxToolsBase** (`sandbox/tool_base.py`)
   - 沙箱工具的基类
   - 处理项目与沙箱的关联
   - 提供沙箱访问的统一接口

## 工具注册机制

### 注册流程

1. **工具初始化**
   ```python
   # 在 agent/run.py 中
   thread_manager.add_tool(SandboxShellTool, project_id=project_id, thread_manager=thread_manager)
   ```

2. **Schema 装饰器**
   - `@openapi_schema`: 定义 OpenAPI 格式的工具描述
   - `@xml_schema`: 定义 XML 格式的工具描述

3. **动态注册**
   - 根据 agent_config 决定启用哪些工具
   - 支持 MCP (Model Context Protocol) 工具的动态加载

## 已实现的工具列表

### 1. SandboxShellTool (执行命令工具)
- **功能**: 在沙箱中执行 shell 命令
- **特点**: 
  - 支持 tmux 会话管理
  - 支持阻塞/非阻塞执行模式
  - 可以检查命令输出和终止运行中的命令
- **方法**:
  - `execute_command`: 执行命令
  - `check_command_output`: 检查输出
  - `terminate_command`: 终止命令
  - `list_commands`: 列出所有会话

### 2. SandboxFilesTool (文件操作工具)
- **功能**: 文件系统操作
- **方法**:
  - `create_file`: 创建文件
  - `str_replace`: 替换文件内容
  - `update_file`: 更新文件
  - `list_directory`: 列出目录
  - `read_file`: 读取文件
  - `delete_file`: 删除文件
  - `move_file`: 移动文件

### 3. SandboxBrowserTool (浏览器工具)
- **功能**: 自动化浏览器操作
- **特点**: 基于 browser-use 库
- **方法**:
  - `use_browser`: 执行浏览器任务
  - `get_browser_state`: 获取浏览器状态

### 4. SandboxVisionTool (视觉工具)
- **功能**: 截图和图像分析
- **方法**:
  - `screenshot`: 截取屏幕或浏览器截图
  - `see_image`: 分析图像内容

### 5. SandboxWebSearchTool (网络搜索工具)
- **功能**: 执行网络搜索
- **方法**:
  - `search_web`: 使用 Tavily API 搜索

### 6. SandboxDeployTool (部署工具)
- **功能**: 部署应用到 Vercel
- **方法**:
  - `deploy_to_vercel`: 部署项目

### 7. SandboxExposeTool (端口暴露工具)
- **功能**: 管理沙箱端口暴露
- **方法**:
  - `expose_port`: 暴露端口
  - `unexpose_port`: 取消暴露
  - `list_exposed_ports`: 列出已暴露端口

### 8. MessageTool (消息工具)
- **功能**: 发送用户消息
- **方法**:
  - `send_message`: 向用户发送消息

### 9. ExpandMessageTool (消息扩展工具)
- **功能**: 展开用户的 @ 引用
- **方法**:
  - `expand_user_message`: 扩展消息内容

### 10. DataProvidersTool (数据提供工具)
- **功能**: 访问各种数据源
- **支持的数据源**:
  - Twitter
  - Yahoo Finance
  - LinkedIn
  - Amazon
  - Zillow
  - Active Jobs

### 11. UpdateAgentTool (更新代理工具)
- **功能**: 更新 AI Agent 配置
- **用途**: Agent Builder 专用

### 12. MCPToolWrapper (MCP 工具包装器)
- **功能**: 动态加载和执行 MCP 工具
- **特点**: 支持 SSE 和 stdio 类型的 MCP 服务器

## 工具调用执行流程

1. **LLM 生成工具调用**
   - OpenAPI 格式: `function_calls`
   - XML 格式: `<function_calls><invoke>...</invoke></function_calls>`

2. **ThreadManager 处理**
   - 解析工具调用请求
   - 从 ToolRegistry 获取工具实例
   - 执行工具方法

3. **结果返回**
   - 使用 ToolResult 封装结果
   - 包含 success 状态和 output 内容

## 前端展示机制

### 工具视图组件架构

前端通过 `tool-views` 目录组织各种工具的展示组件，每个工具类型都有对应的视图组件：

1. **CompleteToolView** (`CompleteToolView.tsx`)
   - 显示任务完成状态
   - 展示任务列表和结果
   - 支持附件显示
   - 进度条动画效果

2. **BrowserToolView** (`BrowserToolView.tsx`)
   - 显示浏览器操作结果
   - 支持截图预览
   - 展示浏览器操作类型（navigate, click, extract 等）

3. **CommandToolView**
   - 显示命令执行结果
   - 支持会话管理
   - 展示命令输出和退出码

4. **FileOperationToolView**
   - 文件操作可视化
   - 根据文件类型显示不同图标
   - 支持语法高亮

5. **WebSearchToolView**
   - 展示搜索结果列表
   - 支持链接预览
   - 显示搜索摘要

6. **DataProviderToolView**
   - 数据源调用结果展示
   - 支持多种数据源格式

7. **DeployToolView**
   - 部署状态展示
   - 显示部署 URL

### 工具数据解析

前端使用多个解析器处理不同格式的工具调用：

1. **XML 解析器** (`xml-parser.ts`)
   - 解析新的 XML 格式：`<function_calls><invoke>...</invoke></function_calls>`
   - 兼容旧格式

2. **工具结果解析器** (`tool-result-parser.ts`)
   - 统一解析工具执行结果
   - 处理 ToolResult 格式

3. **工具工具函数** (`utils.ts`)
   - `extractCommand`: 提取命令
   - `extractFilePath`: 提取文件路径
   - `extractSearchQuery`: 提取搜索查询
   - `extractWebpageContent`: 提取网页内容
   - `normalizeContentToString`: 规范化内容格式
   - `getFileIconAndColor`: 根据文件类型返回图标和颜色

### 工具调用面板

- **tool-call-side-panel.tsx**: 
  - 侧边栏显示工具调用详情
  - 支持展开/折叠查看工具输入输出
  - 实时显示工具执行状态
  - 显示时间戳和执行结果

### 实时流式更新

- 支持流式响应的工具视图更新
- 使用 `isStreaming` 标志控制加载状态
- 支持部分内容的实时展示（如文件内容流式传输）

## 扩展性设计

### 1. 插件式架构

#### 创建新工具的步骤：

1. **继承基类**
   ```python
   from agentpress.tool import Tool, openapi_schema, xml_schema
   
   class MyNewTool(Tool):
       def __init__(self, **kwargs):
           super().__init__()
   ```

2. **定义 Schema**
   ```python
   @openapi_schema({
       "type": "function",
       "function": {
           "name": "my_function",
           "description": "描述",
           "parameters": {...}
       }
   })
   @xml_schema(
       tag_name="my-function",
       mappings=[...],
       example="..."
   )
   async def my_function(self, param1: str) -> ToolResult:
       # 实现逻辑
       return self.success_response(result)
   ```

3. **注册工具**
   ```python
   # 在 run.py 中
   thread_manager.add_tool(MyNewTool, **kwargs)
   ```

### 2. Schema 灵活性

- **双格式支持**: 同一方法可以同时定义 OpenAPI 和 XML schema
- **参数映射**: XML schema 支持灵活的参数映射（元素、属性、内容）
- **向后兼容**: XML 解析器支持严格模式和兼容模式

### 3. MCP (Model Context Protocol) 集成

#### MCP 工具类型：
- **SSE (Server-Sent Events)**: 用于 HTTP 端点
- **stdio**: 用于本地进程通信

#### 动态加载机制：
```python
# MCPToolWrapper 动态创建工具方法
for tool in mcp_tools:
    method = self._create_tool_method(server_name, tool)
    setattr(self, method_name, method)
```

#### 配置示例：
```python
{
    "configured_mcps": [
        {
            "name": "Brave Search",
            "qualifiedName": "mcp_sse_brave_search",
            "config": {
                "url": "https://...",
                "apiKey": "..."
            }
        }
    ],
    "custom_mcps": [
        {
            "name": "Custom Tool",
            "customType": "sse",
            "config": {...}
        }
    ]
}
```

### 4. 工具条件加载

- 基于 agent_config 决定启用哪些工具
- 支持工具级别的权限控制
- 默认模式加载所有工具，自定义 Agent 只加载配置的工具

## 安全性考虑

### 1. 沙箱隔离

- **Daytona 沙箱**: 所有文件和命令操作在隔离的沙箱环境中执行
- **工作目录限制**: 所有路径都相对于 `/workspace` 目录
- **路径清理**: `clean_path` 函数确保路径安全性
- **文件排除**: 自动排除敏感文件（如 `.git`, `node_modules` 等）

### 2. 权限控制

- **项目级别隔离**: 每个工具实例绑定到特定项目 ID
- **会话验证**: 通过 ThreadManager 验证用户权限
- **Agent 配置控制**: 可以在 Agent 级别限制可用工具集
- **账单检查**: 执行前检查用户的计费状态

### 3. 输入验证

#### Schema 级别验证
- OpenAPI schema 定义参数类型、格式和必需性
- XML schema 定义参数映射和验证规则

#### 工具级别验证
- **图像验证**: Base64 图像大小、格式、分辨率检查
- **URL 验证**: 确保 URL 格式正确
- **文件路径验证**: 防止路径遍历攻击
- **命令注入防护**: tmux 会话隔离命令执行

### 4. 输出安全

- **结果截断**: 大输出自动截断（如命令输出限制）
- **敏感信息过滤**: 工具可以实现自定义的输出过滤
- **错误信息处理**: 避免泄露系统敏感信息

## 性能优化

### 1. 并行执行

- 支持并行执行多个工具调用（通过 `tool_execution_strategy`）
- 异步工具方法设计

### 2. 缓存机制

- 沙箱实例缓存，避免重复初始化
- MCP 服务器连接复用

### 3. 流式处理

- 支持流式响应，减少延迟
- 工具结果的增量更新

## 监控和调试

### 1. 日志系统

- 使用统一的 logger 记录工具执行
- 详细的调试日志（通过 logger.debug）
- 错误追踪和异常处理

### 2. 追踪集成

- Langfuse 集成用于性能追踪
- 工具执行时间和结果记录
- 支持会话级别的追踪

### 3. 错误处理

- 统一的 ToolResult 错误格式
- 优雅的降级处理
- 详细的错误信息用于调试
