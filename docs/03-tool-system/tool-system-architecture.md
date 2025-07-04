# Suna 工具系统与 LLM 集成架构详解

## 目录

1. [概述](#概述)
2. [架构设计理念](#架构设计理念)
3. [工具定义与注册机制](#工具定义与注册机制)
4. [双模态格式对比](#双模态格式对比)
5. [LLM 集成与响应处理](#llm-集成与响应处理)
6. [工具执行流程](#工具执行流程)
7. [实际案例分析](#实际案例分析)
8. [架构优势与最佳实践](#架构优势与最佳实践)

## 概述

Suna 是一个先进的 AI Agent 平台，其核心特性之一是强大而灵活的工具系统。该系统允许 LLM（大语言模型）通过标准化接口调用各种工具，从而扩展其能力边界。本文档将深入剖析 Suna 工具系统的设计理念、实现细节和工作流程。

### 核心特点

- **双模态支持**：同时支持 OpenAI Function Calling 和 Anthropic/Cursor XML 格式（详见[双模态格式对比](#双模态格式对比)）
- **动态注册**：根据 Agent 配置动态加载和注册工具
- **沙盒执行**：所有工具在隔离的 Docker 容器中安全执行
- **流式处理**：支持实时解析和执行流式响应中的工具调用
- **可扩展架构**：通过装饰器模式轻松添加新工具

## 架构设计理念

Suna 的工具系统采用了多层抽象的设计模式，实现了关注点的完全分离：

```
┌─────────────────────────────────────────────────────────────┐
│                        应用层 (Agent)                         │
├─────────────────────────────────────────────────────────────┤
│                    线程管理层 (ThreadManager)                  │
├─────────────────────────────────────────────────────────────┤
│                 响应处理层 (ResponseProcessor)                │
├─────────────────────────────────────────────────────────────┤
│                    工具注册层 (ToolRegistry)                   │
├─────────────────────────────────────────────────────────────┤
│                     工具定义层 (Tool Base)                     │
├─────────────────────────────────────────────────────────────┤
│                    执行环境层 (Sandbox RPC)                    │
└─────────────────────────────────────────────────────────────┘
```

每一层都有明确的职责：
- **应用层**：处理用户请求，协调整体流程
- **线程管理层**：管理对话历史，协调 LLM 调用和工具执行
- **响应处理层**：解析 LLM 响应，检测和执行工具调用
- **工具注册层**：统一管理所有可用工具
- **工具定义层**：提供工具实现的基础框架
- **执行环境层**：提供安全隔离的执行环境

## 工具定义与注册机制

### 工具基类设计

所有工具都继承自 `Tool` 抽象基类：

```python
# backend/agentpress/tool.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Dict, List

@dataclass
class ToolResult:
    """工具执行结果的标准化格式"""
    output: Optional[str] = None
    error: Optional[str] = None
    base64_image: Optional[str] = None
    system: Optional[str] = None

class Tool(ABC):
    """工具的抽象基类"""
    
    def __init__(self, agent_id: Optional[str] = None):
        self.agent_id = agent_id
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """返回工具的 OpenAPI schema"""
        pass
    
    @abstractmethod
    def get_xml_tools(self) -> List[Dict[str, Any]]:
        """返回工具的 XML schema"""
        pass
```

### 装饰器模式

Suna 提供了三种装饰器来简化工具定义：

1. **OpenAPI Schema 装饰器**：

```python
# backend/agentpress/tool.py
def openapi_schema(description: str = "", ...):
    """为函数生成 OpenAPI 格式的 schema"""
    def decorator(func):
        # 解析函数签名
        sig = inspect.signature(func)
        
        # 构建参数 schema
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'agent_id']:
                continue
            
            # 从类型注解推断参数类型
            param_type = _get_json_type(param.annotation)
            properties[param_name] = {
                "type": param_type,
                "description": param_descriptions.get(param_name, "")
            }
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        # 生成完整的 OpenAPI schema
        func._schema = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
        
        return func
    return decorator
```

2. **XML Schema 装饰器**：

```python
# backend/agentpress/tool.py
def xml_schema(name: str, attributes: List[str] = [], ...):
    """为函数生成 XML 格式的 schema"""
    def decorator(func):
        func._xml_schema = {
            "name": name,
            "attributes": attributes,
            "elements": elements,
            "description": description
        }
        return func
    return decorator
```

### 工具实现示例

以文件编辑工具为例：

```python
# backend/agent/tools/sb_files_tool.py
class SandboxFilesTool(SandboxToolsBase):
    
    @openapi_schema(
        description="文件内容的字符串替换编辑器",
        path="要编辑的文件路径",
        old_str="要替换的确切字符串",
        new_str="替换后的新字符串"
    )
    @xml_schema(
        name="str_replace_editor",
        attributes=["command", "path"],
        elements=["old_str", "new_str"]
    )
    def str_replace_editor(
        self,
        command: Literal["str_replace"],
        path: str,
        old_str: str,
        new_str: str
    ) -> ToolResult:
        """执行文件内容替换"""
        try:
            # 读取文件内容
            content = self._rpc_call("read_file", {"path": path})
            
            # 检查 old_str 是否存在
            if old_str not in content:
                return ToolResult(error=f"未找到字符串: {old_str}")
            
            # 执行替换
            new_content = content.replace(old_str, new_str, 1)
            
            # 写回文件
            self._rpc_call("write_file", {
                "path": path,
                "content": new_content
            })
            
            return ToolResult(output=f"成功替换 {path} 中的内容")
            
        except Exception as e:
            return ToolResult(error=str(e))
```

### 动态工具注册

工具注册通过 `ToolRegistry` 类管理：

```python
# backend/agentpress/tool_registry.py
class ToolRegistry:
    """工具注册表，管理所有可用工具"""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._openapi_schemas: List[Dict] = []
        self._xml_schemas: List[Dict] = []
        self._function_map: Dict[str, Callable] = {}
    
    def register_tool(self, tool: Tool, only: Optional[List[str]] = None):
        """注册一个工具类"""
        tool_class_name = tool.__class__.__name__
        self.tools[tool_class_name] = tool
        
        # 收集所有带有 schema 的方法
        for name in dir(tool):
            if name.startswith('_'):
                continue
            
            method = getattr(tool, name)
            
            # 如果指定了 only 参数，只注册特定方法
            if only and name not in only:
                continue
            
            # 注册 OpenAPI schema
            if hasattr(method, '_schema'):
                schema = method._schema.copy()
                self._openapi_schemas.append(schema)
                func_name = schema['function']['name']
                self._function_map[func_name] = method
            
            # 注册 XML schema
            if hasattr(method, '_xml_schema'):
                xml_schema = method._xml_schema.copy()
                self._xml_schemas.append(xml_schema)
                xml_name = xml_schema['name']
                self._function_map[xml_name] = method
```

## 双模态格式对比

### OpenAI Function Calling 格式

OpenAI Function Calling 是 OpenAI 推出的标准化工具调用格式，具有以下特点：

**特点：**
- 使用 JSON Schema 定义函数参数
- 通过特定的消息格式调用函数
- 函数返回结果作为独立的消息
- 严格的类型检查和参数验证

**示例：**
```json
// 函数定义
{
  "name": "get_weather",
  "description": "获取指定城市的天气",
  "parameters": {
    "type": "object",
    "properties": {
      "city": {
        "type": "string",
        "description": "城市名称"
      },
      "unit": {
        "type": "string",
        "enum": ["celsius", "fahrenheit"],
        "description": "温度单位"
      }
    },
    "required": ["city"]
  }
}

// LLM 调用格式
{
  "role": "assistant",
  "content": null,
  "function_call": {
    "name": "get_weather",
    "arguments": "{\"city\": \"北京\", \"unit\": \"celsius\"}"
  }
}

// 函数执行结果返回格式
{
  "role": "function",
  "name": "get_weather",
  "content": "{\"temperature\": 25, \"description\": \"晴朗\"}"
}
```

### Anthropic/Cursor XML 格式

Anthropic 和 Cursor 采用的 XML 格式更接近自然语言，具有以下特点：

**特点：**
- 使用 XML 标签嵌入在文本中
- 更自然的对话流程
- 可以在一条消息中包含多个函数调用
- 支持流式解析和实时执行

**示例：**
```xml
我来查询一下北京的天气。

<function_calls>
<invoke name="get_weather">
<parameter name="city">北京</parameter>
<parameter name="unit">celsius</parameter>
</invoke>
</function_calls>

根据查询结果，北京当前温度是 25°C，天气晴朗。

现在我再查询一下上海的天气。

<function_calls>
<invoke name="get_weather">
<parameter name="city">上海</parameter>
<parameter name="unit">celsius</parameter>
</invoke>
</function_calls>

上海当前温度是 28°C，有些多云。
```

### 主要区别对比

| 特性 | OpenAI Function Calling | Anthropic/Cursor XML |
|------|------------------------|---------------------|
| **格式** | JSON | XML |
| **调用方式** | 独立的消息类型 | 嵌入在文本中 |
| **参数传递** | JSON 字符串 | XML 元素 |
| **多函数调用** | 需要多个消息往返 | 单条消息可包含多个调用 |
| **可读性** | 结构化但较技术性 | 更自然、易读 |
| **流式处理** | 需要等待完整响应 | 支持实时解析和执行 |
| **错误处理** | JSON 解析错误 | XML 解析错误 |
| **上下文保持** | 函数调用独立于对话 | 函数调用与对话内容交织 |

### 实际应用场景

**OpenAI Function Calling 适合：**
- 需要严格类型检查的场景
- 与 OpenAI API 集成
- 需要明确区分对话和函数调用
- 企业级应用的标准化接口

**Anthropic/Cursor XML 适合：**
- 更自然的对话流程
- 需要在单条响应中执行多个操作
- 与 Claude/Cursor 等工具集成
- 实时流式处理场景

### 双模态支持的优势

Suna 同时支持两种格式，带来了以下优势：

1. **兼容性**：可以同时支持使用不同格式的客户端和 LLM 提供商
2. **灵活性**：根据具体场景选择最合适的格式
3. **平滑迁移**：从一种格式迁移到另一种格式时不需要重写整个系统
4. **生态系统集成**：可以更容易地集成到不同的 AI 工具链中
5. **性能优化**：XML 格式支持流式解析，可以实现更低的延迟

### Suna 中的实现

在 Suna 中，通过统一的工具定义和双装饰器模式，一个工具可以同时支持两种调用格式：

```python
class SandboxFilesTool(SandboxToolsBase):
    
    @openapi_schema(
        description="文件内容的字符串替换编辑器",
        path="要编辑的文件路径",
        old_str="要替换的确切字符串",
        new_str="替换后的新字符串"
    )
    @xml_schema(
        name="str_replace_editor",
        attributes=["command", "path"],
        elements=["old_str", "new_str"]
    )
    def str_replace_editor(
        self,
        command: Literal["str_replace"],
        path: str,
        old_str: str,
        new_str: str
    ) -> ToolResult:
        """执行文件内容替换"""
        # 实现代码...
```

这种设计使得同一个工具函数可以被两种格式调用，大大提高了系统的通用性和可维护性。

关于两种格式的详细 API 请求示例和代码实现，请参考 [工具调用 API 请求示例](./tool-calling-api-examples.md) 文档。

## LLM 集成与响应处理

### LLM 服务层

Suna 使用 LiteLLM 作为统一的 LLM 接口：

```python
# backend/services/llm.py
class LLMService:
    """统一的 LLM 服务接口"""
    
    async def chat_completion(
        self,
        messages: List[Dict],
        model: str,
        tools: Optional[List[Dict]] = None,
        stream: bool = False,
        **kwargs
    ):
        """调用 LLM API"""
        # 准备请求参数
        params = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }
        
        # 如果有工具定义，添加到请求中
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        
        # 调用 LiteLLM
        response = await litellm.acompletion(**params)
        
        if stream:
            return self._handle_stream(response)
        else:
            return response
```

### 响应处理器

`ResponseProcessor` 负责解析 LLM 响应并执行工具调用：

```python
# backend/agentpress/response_processor.py
class ResponseProcessor:
    """处理 LLM 响应，检测和执行工具调用"""
    
    def __init__(
        self,
        tool_registry: ToolRegistry,
        xml_parser: XMLToolParser,
        execution_mode: str = "sequential"
    ):
        self.tool_registry = tool_registry
        self.xml_parser = xml_parser
        self.execution_mode = execution_mode
    
    async def process_response(
        self,
        response: Any,
        stream: bool = False
    ) -> ProcessedResponse:
        """处理 LLM 响应"""
        if stream:
            return await self._process_stream(response)
        else:
            return await self._process_non_stream(response)
    
    async def _process_stream(self, response_stream):
        """处理流式响应"""
        content_buffer = ""
        tool_calls_detected = False
        
        async for chunk in response_stream:
            # 累积内容
            if chunk.choices[0].delta.content:
                content_buffer += chunk.choices[0].delta.content
            
            # 检测原生工具调用
            if chunk.choices[0].delta.tool_calls:
                tool_calls_detected = True
                yield ProcessingState(
                    type="tool_detected",
                    data=chunk.choices[0].delta.tool_calls
                )
            
            # 实时检测 XML 工具调用
            if not tool_calls_detected:
                xml_tools = self.xml_parser.extract_tool_calls(content_buffer)
                if xml_tools:
                    # 立即执行检测到的工具
                    for tool_call in xml_tools:
                        result = await self._execute_tool(tool_call)
                        yield ProcessingState(
                            type="tool_result",
                            data=result
                        )
            
            # 输出内容块
            yield ProcessingState(
                type="content",
                data=chunk.choices[0].delta.content
            )
```

### XML 工具解析器

支持 Cursor 风格的 XML 工具调用：

```python
# backend/agentpress/xml_tool_parser.py
class XMLToolParser:
    """解析 XML 格式的工具调用"""
    
    # Cursor 风格的正则表达式
    CURSOR_PATTERN = re.compile(
        r'<function_calls>\s*<invoke\s+name="([^"]+)">(.*?)</invoke>\s*</function_calls>',
        re.DOTALL
    )
    
    def extract_tool_calls(self, content: str) -> List[ToolCall]:
        """从内容中提取工具调用"""
        tool_calls = []
        
        # 尝试 Cursor 格式
        for match in self.CURSOR_PATTERN.finditer(content):
            tool_name = match.group(1)
            params_xml = match.group(2)
            
            # 解析参数
            params = self._parse_parameters(params_xml, tool_name)
            
            tool_calls.append(ToolCall(
                name=tool_name,
                parameters=params,
                format="cursor_xml"
            ))
        
        return tool_calls
    
    def _parse_parameters(self, params_xml: str, tool_name: str) -> Dict:
        """解析工具参数"""
        params = {}
        
        # 获取工具的 XML schema
        schema = self._get_xml_schema(tool_name)
        
        # 解析属性参数
        if schema.get('attributes'):
            # 从 invoke 标签中提取属性
            ...
        
        # 解析元素参数
        if schema.get('elements'):
            for element in schema['elements']:
                pattern = rf'<{element}>(.*?)</{element}>'
                match = re.search(pattern, params_xml, re.DOTALL)
                if match:
                    params[element] = match.group(1)
        
        return params
```

## 工具执行流程

### 完整的执行流程

1. **准备阶段**：

```python
# backend/agentpress/thread_manager.py
class ThreadManager:
    async def send_message(self, content: str, files: List = None):
        """发送消息并获取 AI 响应"""
        # 1. 构建消息
        message = self._build_message(content, files)
        
        # 2. 获取工具 schemas
        tools = self.tool_registry.get_openapi_schemas()
        
        # 3. 准备系统提示（包含 XML 工具格式说明）
        system_prompt = self._build_system_prompt()
        
        # 4. 调用 LLM
        response = await self.llm_service.chat_completion(
            messages=self.messages + [message],
            model=self.model,
            tools=tools,
            stream=self.stream
        )
        
        # 5. 处理响应
        return await self._process_response(response)
```

2. **工具检测阶段**：

```python
async def _process_response(self, response):
    """处理 LLM 响应"""
    processor = ResponseProcessor(
        self.tool_registry,
        self.xml_parser,
        execution_mode=self.execution_mode
    )
    
    async for state in processor.process_response(response, self.stream):
        if state.type == "tool_detected":
            # 原生工具调用检测
            self._emit_event("tool_detected", state.data)
        
        elif state.type == "xml_tool_detected":
            # XML 工具调用检测
            self._emit_event("xml_tool_detected", state.data)
        
        elif state.type == "tool_result":
            # 工具执行结果
            await self._handle_tool_result(state.data)
        
        elif state.type == "content":
            # 普通内容
            self._emit_event("content", state.data)
```

3. **工具执行阶段**：

```python
# backend/agentpress/response_processor.py
async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
    """执行单个工具调用"""
    try:
        # 获取工具函数
        func = self.tool_registry.get_function(tool_call.name)
        if not func:
            return ToolResult(error=f"未找到工具: {tool_call.name}")
        
        # 验证参数
        validated_params = self._validate_parameters(
            func,
            tool_call.parameters
        )
        
        # 执行工具
        if asyncio.iscoroutinefunction(func):
            result = await func(**validated_params)
        else:
            result = func(**validated_params)
        
        # 确保返回 ToolResult
        if not isinstance(result, ToolResult):
            result = ToolResult(output=str(result))
        
        return result
        
    except Exception as e:
        logger.error(f"工具执行错误: {e}")
        return ToolResult(error=str(e))
```

4. **结果处理阶段**：

```python
async def _handle_tool_result(self, result: ToolResult):
    """处理工具执行结果"""
    # 根据结果处理策略决定如何集成结果
    if self.result_handling == "append":
        # 将结果作为新消息添加
        self.messages.append({
            "role": "tool",
            "content": result.output or result.error
        })
    
    elif self.result_handling == "replace":
        # 替换当前消息内容
        self.current_message['content'] += f"\n\n{result.output}"
    
    elif self.result_handling == "xml":
        # 以 XML 格式返回结果
        result_xml = f"""
<result>
{result.output}
</result>
        """
        self.current_message['content'] += result_xml
```

### 执行模式

Suna 支持多种工具执行模式：

1. **顺序执行**：按照检测顺序依次执行工具
2. **并行执行**：同时执行多个独立的工具调用
3. **流式执行**：在流式响应中实时执行工具
4. **批量执行**：收集所有工具调用后统一执行

```python
# backend/agentpress/response_processor.py
async def _execute_tools(self, tool_calls: List[ToolCall]):
    """根据执行模式执行工具"""
    if self.execution_mode == "parallel":
        # 并行执行
        tasks = [
            self._execute_tool(tc) 
            for tc in tool_calls
        ]
        results = await asyncio.gather(*tasks)
        
    elif self.execution_mode == "sequential":
        # 顺序执行
        results = []
        for tc in tool_calls:
            result = await self._execute_tool(tc)
            results.append(result)
    
    return results
```

## 实际案例分析

### 案例1：文件编辑操作

当用户要求编辑文件时，完整的流程如下：

1. **用户请求**：
```
用户: 请将 main.py 中的 print("Hello") 改为 print("Hello, World!")
```

2. **LLM 生成工具调用**：
```xml
<function_calls>
<invoke name="str_replace_editor">
<parameter name="command">str_replace</parameter>
<parameter name="path">main.py</parameter>
<parameter name="old_str">print("Hello")</parameter>
<parameter name="new_str">print("Hello, World!")</parameter>
</invoke>
</function_calls>
```

3. **工具执行**：
```python
# 1. XML 解析器提取工具调用
tool_call = ToolCall(
    name="str_replace_editor",
    parameters={
        "command": "str_replace",
        "path": "main.py",
        "old_str": 'print("Hello")',
        "new_str": 'print("Hello, World!")'
    }
)

# 2. 工具注册表查找对应函数
func = tool_registry.get_function("str_replace_editor")

# 3. 执行工具（在沙盒中）
result = await func(**tool_call.parameters)

# 4. 返回结果
ToolResult(output="成功替换 main.py 中的内容")
```

### 案例2：并行工具执行

当需要同时执行多个操作时：

```python
# LLM 可能生成多个工具调用
response = """
让我帮你创建项目结构。

<function_calls>
<invoke name="create_directory">
<parameter name="path">src</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="create_directory">
<parameter name="path">tests</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="create_file">
<parameter name="path">src/__init__.py</parameter>
<parameter name="content"></parameter>
</invoke>
</function_calls>
"""

# ResponseProcessor 会：
# 1. 检测所有工具调用
# 2. 并行执行（如果配置为并行模式）
# 3. 收集所有结果
# 4. 统一返回
```

### 案例3：MCP 工具集成

Suna 支持动态加载 MCP（Model Context Protocol）工具：

```python
# backend/agent/tools/mcp_tool_wrapper.py
class MCPToolWrapper(Tool):
    """MCP 工具的动态包装器"""
    
    def __init__(self, mcp_client, tool_definitions):
        self.mcp_client = mcp_client
        
        # 动态创建工具方法
        for tool_def in tool_definitions:
            method = self._create_tool_method(tool_def)
            setattr(self, tool_def['name'], method)
            
            # 添加 schema
            method._schema = self._convert_to_openapi(tool_def)
    
    def _create_tool_method(self, tool_def):
        """为 MCP 工具创建方法"""
        async def tool_method(**kwargs):
            # 调用 MCP 服务器
            result = await self.mcp_client.call_tool(
                tool_def['name'],
                kwargs
            )
            return ToolResult(output=result)
        
        return tool_method
```

## 架构优势与最佳实践

### 架构优势

1. **灵活性**：
   - 支持多种 LLM 提供商和工具调用格式
   - 可以轻松添加新的工具和调用格式
   - 支持自定义执行策略

2. **安全性**：
   - 所有工具在 Docker 容器中隔离执行
   - 完整的权限控制和资源限制
   - 错误隔离，不会影响主进程

3. **性能**：
   - 支持并行执行提高效率
   - 流式处理减少延迟
   - 智能缓存减少重复调用

4. **可维护性**：
   - 清晰的分层架构
   - 统一的错误处理
   - 完善的日志和监控

### 最佳实践

1. **工具设计**：
   - 保持工具功能单一和明确
   - 提供清晰的参数描述
   - 返回结构化的结果

2. **错误处理**：
   - 始终返回 ToolResult 对象
   - 提供有意义的错误信息
   - 实现重试机制

3. **性能优化**：
   - 对于独立的操作使用并行执行
   - 实现结果缓存
   - 避免在工具中执行长时间操作

4. **安全考虑**：
   - 验证所有输入参数
   - 限制文件系统访问范围
   - 监控资源使用

## 总结

Suna 的工具系统通过精心设计的多层架构，实现了 LLM 与外部工具的无缝集成。其双模态支持、动态注册、安全执行等特性，使其成为构建强大 AI Agent 的理想平台。通过本文档的详细分析，我们可以看到：

1. **统一抽象**：通过 Tool 基类和装饰器模式，简化了工具的定义和注册
2. **灵活解析**：支持多种工具调用格式，适配不同的 LLM 提供商
3. **安全执行**：通过沙盒隔离确保工具执行的安全性
4. **高效处理**：支持流式和并行执行，优化性能表现

这种架构设计不仅满足了当前的需求，也为未来的扩展留下了充分的空间。无论是添加新的工具类型、支持新的 LLM 格式，还是优化执行策略，都可以在不影响现有代码的情况下轻松实现。

## 相关文档

- [工具系统总览](./tool-system-overview.md) - 工具列表和使用指南
- [双模态调用系统](./dual-mode-tool-calling.md) - OpenAI 和 Anthropic 格式详解
- [工具调用 API 示例](./tool-calling-api-examples.md) - 具体的 API 使用示例
- [ThreadManager 分析](../02-core-architecture/thread-manager-analysis.md) - 了解工具系统的集成方式
- [MCP 集成](../04-extension-systems/mcp-integration.md) - MCP 工具的动态加载