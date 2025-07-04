# Suna 工具系统完整指南

本文档全面介绍 Suna 的工具系统，包括工具列表、架构设计、使用方法和扩展指南。

## 📋 工具列表概览

Suna 系统包含 **12 个核心工具**，分为以下几类：

### 🖥️ 系统与文件操作
| 工具名称 | 定义文件 | 功能描述 |
|---------|---------|---------|
| **SandboxShellTool** | `sb_shell_tool.py` | 执行命令行命令，支持 tmux 会话管理 |
| **SandboxFilesTool** | `sb_files_tool.py` | 文件增删改查、目录操作 |

### 🌐 Web 相关
| 工具名称 | 定义文件 | 功能描述 |
|---------|---------|---------|
| **SandboxBrowserTool** | `sb_browser_tool.py` | 浏览器自动化（截图、点击、输入等） |
| **SandboxWebSearchTool** | `web_search_tool.py` | 使用 Tavily API 进行网络搜索 |
| **SandboxDeployTool** | `sb_deploy_tool.py` | 部署应用到 Vercel |

### 👁️ 视觉与展示
| 工具名称 | 定义文件 | 功能描述 |
|---------|---------|---------|
| **SandboxVisionTool** | `sb_vision_tool.py` | 截屏和图像查看 |
| **SandboxExposeTool** | `sb_expose_tool.py` | 暴露本地端口到公网 |

### 💬 消息与通信
| 工具名称 | 定义文件 | 功能描述 |
|---------|---------|---------|
| **MessageTool** | `message_tool.py` | 发送格式化消息给用户 |
| **ExpandMessageTool** | `expand_msg_tool.py` | 扩展消息长度限制 |

### 🔌 扩展与集成
| 工具名称 | 定义文件 | 功能描述 |
|---------|---------|---------|
| **DataProvidersTool** | `data_providers_tool.py` | 访问多种数据源（LinkedIn、Twitter等） |
| **UpdateAgentTool** | `update_agent_tool.py` | 动态更新 Agent 配置 |
| **MCPToolWrapper** | `mcp_tool_wrapper.py` | 动态加载 MCP 协议工具 |

## 🏗️ 工具系统架构

### 1. 整体架构图

```mermaid
graph TB
    subgraph "客户端"
        User[用户] --> UI[Web UI / CLI]
    end
    
    subgraph "应用层"
        UI --> Agent[Agent Service]
        Agent --> TM[ThreadManager]
    end
    
    subgraph "处理层"
        TM --> LLM[LLM Service]
        TM --> RP[ResponseProcessor]
        RP --> XP[XMLToolParser]
    end
    
    subgraph "工具层"
        RP --> TR[ToolRegistry]
        TR --> Tools[工具实现]
        Tools --> FT[文件工具]
        Tools --> CT[命令工具]
        Tools --> MT[MCP工具]
    end
    
    subgraph "执行层"
        Tools --> RPC[Sandbox RPC]
        RPC --> Docker[Docker容器]
    end
    
    style User fill:#f9f,stroke:#333,stroke-width:2px
    style Docker fill:#9f9,stroke:#333,stroke-width:2px
```

### 2. 工具基类定义

**文件**: `backend/agentpress/tool.py`

```python
class Tool:
    """所有工具的抽象基类"""
    
    def definition(self) -> dict:
        """返回工具定义（OpenAPI 格式）"""
        pass
    
    def xml_definition(self) -> dict:
        """返回 XML 格式的工具定义"""
        pass
    
    def execute(self, context: Any) -> dict:
        """执行工具的抽象方法"""
        raise NotImplementedError
```

### 3. 沙箱工具基类

**文件**: `backend/sandbox/tool_base.py`

```python
class SandboxToolsBase(Tool):
    """沙箱环境中工具的基类"""
    
    def __init__(self, sandbox, thread_id, user_id):
        self.sandbox = sandbox
        self.thread_id = thread_id
        self.user_id = user_id
        self.api_url = sandbox.api_url
```

### 4. 工具注册机制

**文件**: `backend/agentpress/tool_registry.py`

```python
class ToolRegistry:
    """工具注册中心"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register_tool(self, tool: Tool):
        """注册工具到系统"""
        for method_name in tool.get_methods():
            self._tools[method_name] = tool
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """获取工具实例"""
        return self._tools.get(tool_name)
```

## 🔧 工具定义方式

### 1. 使用装饰器定义

```python
class SandboxFilesTool(SandboxToolsBase):
    
    @method()
    @argument("path", str, "文件路径", required=True)
    @argument("content", str, "文件内容", required=True)
    def write(self, path: str, content: str) -> dict:
        """写入文件"""
        # 实现逻辑
        pass
```

### 2. Schema 生成

工具会自动生成两种格式的 Schema：

**OpenAPI 格式**:
```json
{
    "title": "write",
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "文件路径"},
        "content": {"type": "string", "description": "文件内容"}
    },
    "required": ["path", "content"]
}
```

**XML 格式**:
```xml
<write>
    <path>文件路径</path>
    <content>文件内容</content>
</write>
```

## 🚀 工具执行流程

### 1. LLM 调用流程图

```mermaid
sequenceDiagram
    participant U as 用户
    participant TM as ThreadManager
    participant LLM as LLM Service
    participant RP as ResponseProcessor
    participant TR as ToolRegistry
    participant T as Tool
    participant S as Sandbox
    
    U->>TM: 发送消息
    TM->>TR: 获取工具Schemas
    TR-->>TM: 返回Schemas
    TM->>LLM: 调用LLM API(含工具定义)
    LLM-->>TM: 返回响应(含工具调用)
    TM->>RP: 处理响应
    
    alt 检测到工具调用
        RP->>TR: 查找工具函数
        TR-->>RP: 返回函数引用
        RP->>T: 执行工具
        T->>S: RPC调用
        S-->>T: 返回结果
        T-->>RP: 返回ToolResult
        RP-->>TM: 返回处理结果
    else 普通文本响应
        RP-->>TM: 返回文本内容
    end
    
    TM-->>U: 显示结果
```

### 2. 工具执行模式对比

```mermaid
graph TB
    subgraph "顺序执行"
        A1[工具1] --> A2[工具2]
        A2 --> A3[工具3]
        A3 --> A4[结果汇总]
    end
    
    subgraph "并行执行"
        B0[分发] --> B1[工具1]
        B0 --> B2[工具2]
        B0 --> B3[工具3]
        B1 --> B4[结果汇总]
        B2 --> B4
        B3 --> B4
    end
    
    subgraph "流式执行"
        C1[检测工具1] --> C2[执行工具1]
        C2 --> C3[输出结果1]
        C3 --> C4[检测工具2]
        C4 --> C5[执行工具2]
        C5 --> C6[输出结果2]
    end
```

## 📦 具体工具实现示例

### SandboxBrowserTool - 浏览器自动化

```python
class SandboxBrowserTool(SandboxToolsBase):
    
    @method()
    @argument("url", str, "要访问的URL", required=True)
    def navigate(self, url: str) -> dict:
        """导航到指定URL"""
        response = requests.post(
            f"{self.api_url}/browser/navigate",
            json={"url": url}
        )
        return {"status": "success", "url": url}
    
    @method()
    @argument("selector", str, "CSS选择器", required=True)
    def click(self, selector: str) -> dict:
        """点击页面元素"""
        response = requests.post(
            f"{self.api_url}/browser/click",
            json={"selector": selector}
        )
        return {"status": "clicked", "selector": selector}
```

## 🎨 前端工具展示

### 工具调用的 UI 组件

**文件路径**: `frontend/src/components/thread/tool-views/`

每个工具都有对应的视图组件：
- `BrowserToolView.tsx` - 浏览器操作展示
- `FileOperationToolView.tsx` - 文件操作展示
- `CommandToolView.tsx` - 命令执行展示
- `WebSearchToolView.tsx` - 搜索结果展示

### 工具结果解析

**文件**: `frontend/src/components/thread/tool-views/tool-result-parser.ts`

```typescript
export function parseToolResult(toolName: string, result: any) {
    switch (toolName) {
        case 'navigate':
            return <BrowserView url={result.url} />;
        case 'write':
            return <FileView path={result.path} />;
        // ... 其他工具
    }
}
```

## 🔒 安全机制

### 1. 沙盒执行架构

```mermaid
graph TB
    subgraph "主进程"
        Tool[工具实例] --> RPC[RPC客户端]
    end
    
    subgraph "Docker容器"
        RPCS[RPC服务器] --> FS[文件系统]
        RPCS --> CMD[命令执行]
        RPCS --> NET[网络访问]
        
        FS --> WS[workspace目录]
        CMD --> SH[Shell环境]
    end
    
    RPC -.RPC调用.-> RPCS
    RPCS -.返回结果.-> RPC
    
    style WS fill:#ffd,stroke:#333,stroke-width:2px
    style Docker容器 fill:#eef,stroke:#333,stroke-width:2px
```

### 2. 安全措施

1. **沙箱隔离**
   - 所有工具在 Daytona 沙箱中执行
   - 限制文件系统访问范围
   - 网络访问控制

2. **权限验证**
   - 每个工具调用都验证用户权限
   - 基于项目的访问控制
   - API 密钥验证

3. **输入验证**
   - 参数类型检查
   - 路径遍历防护
   - 命令注入防护

## 🛠️ 扩展新工具

### 1. 创建工具类

```python
# backend/agent/tools/my_custom_tool.py
from sandbox.tool_base import SandboxToolsBase
from agentpress.tool import method, argument

class MyCustomTool(SandboxToolsBase):
    
    @method()
    @argument("param1", str, "参数说明", required=True)
    def my_method(self, param1: str) -> dict:
        # 实现逻辑
        return {"result": "success"}
```

### 2. 注册工具

```python
# 在工具加载时注册
def register_tools(thread_manager, sandbox):
    tools = [
        MyCustomTool(sandbox, thread_id, user_id),
        # 其他工具...
    ]
    
    for tool in tools:
        thread_manager.tool_registry.register_tool(tool)
```

### 3. 创建前端视图

```typescript
// frontend/src/components/thread/tool-views/MyCustomToolView.tsx
export function MyCustomToolView({ result }: { result: any }) {
    return (
        <div className="tool-result">
            <h3>My Custom Tool Result</h3>
            <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
    );
}
```

## 🔄 MCP 工具集成

MCP (Model Context Protocol) 允许动态加载第三方工具：

### 1. MCP 工具集成流程

```mermaid
graph TD
    A[MCP配置] --> B[启动MCP服务器]
    B --> C[获取工具列表]
    C --> D[创建MCPToolWrapper]
    
    D --> E[动态生成方法]
    E --> F[添加OpenAPI Schema]
    F --> G[注册到ToolRegistry]
    
    G --> H[工具可用]
    
    H --> I{调用工具}
    I --> J[MCPClient.call_tool]
    J --> K[MCP服务器执行]
    K --> L[返回结果]
    L --> M[封装为ToolResult]
```

### 2. 配置示例

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem"]
    }
  }
}
```

## 📊 工具使用统计

系统会跟踪工具使用情况：
- 调用次数
- 执行时间
- 成功/失败率
- 资源消耗

这些数据可用于：
- 优化性能
- 改进工具设计
- 使用量计费

## 🎯 最佳实践

### 1. 错误处理流程

```mermaid
graph TD
    A[工具调用] --> B{执行阶段}
    
    B -->|参数验证| C{参数有效?}
    C -->|否| D[返回参数错误]
    C -->|是| E[执行工具函数]
    
    B -->|工具执行| E
    E --> F{执行成功?}
    F -->|否| G[捕获异常]
    F -->|是| H[返回成功结果]
    
    G --> I[记录日志]
    I --> J[返回错误信息]
    
    D --> K[ToolResult.error]
    J --> K
    H --> L[ToolResult.output]
    
    style D fill:#fdd,stroke:#333,stroke-width:2px
    style J fill:#fdd,stroke:#333,stroke-width:2px
    style H fill:#dfd,stroke:#333,stroke-width:2px
```

### 2. 性能优化策略

```mermaid
graph TB
    subgraph "并行优化"
        P1[识别独立操作]
        P2[创建任务组]
        P3[asyncio.gather执行]
        P4[合并结果]
        P1 --> P2 --> P3 --> P4
    end
    
    subgraph "缓存优化"
        C1[工具结果缓存]
        C2[LLM响应缓存]
        C3[Schema缓存]
        C1 --> C4[减少重复执行]
        C2 --> C4
        C3 --> C4
    end
    
    subgraph "流式优化"
        S1[增量解析]
        S2[即时执行]
        S3[流式输出]
        S1 --> S2 --> S3
        S3 --> S4[降低延迟]
    end
```

### 3. 开发建议

1. **错误处理**
   - 总是返回结构化的错误信息
   - 提供有用的错误描述
   - 记录详细的错误日志

2. **性能优化**
   - 使用流式处理大文件
   - 实现结果缓存
   - 避免阻塞操作

3. **用户体验**
   - 提供清晰的进度反馈
   - 支持操作取消
   - 返回易于理解的结果

## 相关文档

- [工具系统架构详解](./tool-system-architecture.md) - 深入了解架构设计
- [工具调用 API 示例](./tool-calling-api-examples.md) - 具体的 API 使用示例
- [双模态调用系统](./dual-mode-tool-calling-system-analysis.md) - OpenAI 和 Anthropic 格式支持
- [沙盒工具指南](./sandboxshelltool-guide.md) - 安全执行环境详解
- [Daytona tmux 集成](./daytona-tmux-integration.md) - Daytona 与 tmux 的集成方案

通过这个强大的工具系统，Suna 能够执行各种复杂的任务，从简单的文件操作到复杂的网页自动化，为用户提供真正的 AI 助手体验。