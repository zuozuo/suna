# 工具调用 API 请求示例

本文档详细展示了 OpenAI Function Calling 和 Anthropic/Cursor XML 两种工具调用格式的 API 请求示例，帮助开发者理解和使用这两种不同的模态。

## 目录

1. [OpenAI Function Calling 格式](#openai-function-calling-格式)
   - [Python 示例](#python-示例)
   - [cURL 示例](#curl-示例)
2. [Anthropic/Cursor XML 格式](#anthropiccursor-xml-格式)
   - [Python 示例](#python-示例-1)
   - [流式处理示例](#流式处理示例)
   - [cURL 示例](#curl-示例-1)
3. [关键区别总结](#关键区别总结)
4. [在 Suna 中的使用](#在-suna-中的使用)

## OpenAI Function Calling 格式

### Python 示例

```python
import openai
import json

# 初始化 OpenAI 客户端
client = openai.OpenAI(api_key="your-api-key")

# 定义工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
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
    }
]

# 发送请求
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "北京今天天气怎么样？"}
    ],
    tools=tools,
    tool_choice="auto"  # 自动决定是否调用工具
)

# 处理响应
message = response.choices[0].message

if message.tool_calls:
    # LLM 决定调用工具
    tool_call = message.tool_calls[0]
    function_name = tool_call.function.name
    function_args = json.loads(tool_call.function.arguments)
    
    print(f"调用函数: {function_name}")
    print(f"参数: {function_args}")
    
    # 模拟函数执行
    if function_name == "get_weather":
        weather_result = {
            "temperature": 25,
            "description": "晴朗",
            "humidity": 60
        }
    
    # 将函数结果返回给 LLM
    follow_up = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": "北京今天天气怎么样？"},
            message,  # 包含工具调用的助手消息
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(weather_result)
            }
        ]
    )
    
    print(f"最终回复: {follow_up.choices[0].message.content}")
```

### cURL 示例

```bash
# 第一次请求 - 发送用户消息和工具定义
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "北京今天天气怎么样？"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "获取指定城市的天气信息",
          "parameters": {
            "type": "object",
            "properties": {
              "city": {"type": "string", "description": "城市名称"},
              "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["city"]
          }
        }
      }
    ],
    "tool_choice": "auto"
  }'

# 响应示例
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "get_weather",
          "arguments": "{\"city\": \"北京\", \"unit\": \"celsius\"}"
        }
      }]
    }
  }]
}

# 第二次请求 - 发送工具执行结果
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "北京今天天气怎么样？"},
      {
        "role": "assistant",
        "content": null,
        "tool_calls": [{
          "id": "call_abc123",
          "type": "function",
          "function": {
            "name": "get_weather",
            "arguments": "{\"city\": \"北京\", \"unit\": \"celsius\"}"
          }
        }]
      },
      {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "content": "{\"temperature\": 25, \"description\": \"晴朗\", \"humidity\": 60}"
      }
    ]
  }'
```

### 处理多个工具调用

```python
# OpenAI 支持在一次响应中调用多个工具
if message.tool_calls:
    tool_results = []
    
    for tool_call in message.tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        # 根据不同的工具执行不同的逻辑
        if function_name == "get_weather":
            result = get_weather(**function_args)
        elif function_name == "search_web":
            result = search_web(**function_args)
        
        tool_results.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result)
        })
    
    # 批量返回所有工具结果
    follow_up = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": original_message},
            message,
            *tool_results  # 展开所有工具结果
        ]
    )
```

## Anthropic/Cursor XML 格式

### Python 示例

```python
import anthropic
import re
import xml.etree.ElementTree as ET

# 初始化 Anthropic 客户端
client = anthropic.Anthropic(api_key="your-api-key")

# 系统提示，说明工具的使用方式
system_prompt = """你是一个有用的助手。你可以使用以下工具：

<tools>
<tool name="get_weather">
  <description>获取指定城市的天气信息</description>
  <parameters>
    <parameter name="city" type="string" required="true">城市名称</parameter>
    <parameter name="unit" type="string" required="false">温度单位 (celsius/fahrenheit)</parameter>
  </parameters>
</tool>
</tools>

当你需要调用工具时，请使用以下格式：
<function_calls>
<invoke name="tool_name">
<parameter name="param_name">param_value</parameter>
</invoke>
</function_calls>
"""

# 发送请求
response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1000,
    system=system_prompt,
    messages=[
        {"role": "user", "content": "北京今天天气怎么样？"}
    ]
)

# 解析响应中的工具调用
content = response.content[0].text
print(f"助手回复: {content}")

# 使用正则表达式查找工具调用
tool_call_pattern = r'<function_calls>\s*<invoke\s+name="([^"]+)">(.*?)</invoke>\s*</function_calls>'
matches = re.findall(tool_call_pattern, content, re.DOTALL)

if matches:
    for tool_name, params_xml in matches:
        print(f"\n检测到工具调用: {tool_name}")
        
        # 解析参数
        params = {}
        param_pattern = r'<parameter\s+name="([^"]+)">([^<]+)</parameter>'
        param_matches = re.findall(param_pattern, params_xml)
        
        for param_name, param_value in param_matches:
            params[param_name] = param_value.strip()
        
        print(f"参数: {params}")
        
        # 模拟执行工具
        if tool_name == "get_weather":
            weather_result = {
                "temperature": 25,
                "description": "晴朗",
                "humidity": 60
            }
            
            # 继续对话，包含工具结果
            follow_up = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": "北京今天天气怎么样？"},
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": f"<result>{weather_result}</result>"}
                ]
            )
            
            print(f"\n最终回复: {follow_up.content[0].text}")
```

### 流式处理示例

```python
import anthropic
import asyncio
import re

class StreamingXMLParser:
    """实时解析流式响应中的 XML 工具调用"""
    
    def __init__(self):
        self.buffer = ""
        self.in_function_call = False
        
    def parse_chunk(self, chunk):
        """解析流式块，提取完整的工具调用"""
        self.buffer += chunk
        
        # 检查是否有完整的工具调用
        pattern = r'<function_calls>(.*?)</function_calls>'
        matches = re.findall(pattern, self.buffer, re.DOTALL)
        
        for match in matches:
            # 解析工具调用
            invoke_pattern = r'<invoke\s+name="([^"]+)">(.*?)</invoke>'
            invoke_matches = re.findall(invoke_pattern, match, re.DOTALL)
            
            for tool_name, params_xml in invoke_matches:
                params = self._parse_parameters(params_xml)
                yield {
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "parameters": params
                }
            
            # 从缓冲区中移除已处理的工具调用
            self.buffer = self.buffer.replace(f'<function_calls>{match}</function_calls>', '')
    
    def _parse_parameters(self, params_xml):
        """解析工具参数"""
        params = {}
        param_pattern = r'<parameter\s+name="([^"]+)">([^<]+)</parameter>'
        matches = re.findall(param_pattern, params_xml)
        for name, value in matches:
            params[name] = value.strip()
        return params

# 异步工具执行函数
async def execute_tool(tool_call):
    """模拟异步工具执行"""
    if tool_call["tool_name"] == "get_weather":
        # 模拟 API 调用延迟
        await asyncio.sleep(1)
        return {
            "temperature": 25,
            "description": "晴朗",
            "city": tool_call["parameters"].get("city", "未知")
        }
    return {"error": "Unknown tool"}

# 流式处理主函数
async def stream_with_tools():
    client = anthropic.AsyncAnthropic(api_key="your-api-key")
    parser = StreamingXMLParser()
    
    system_prompt = """当需要获取天气信息时，使用以下格式：
<function_calls>
<invoke name="get_weather">
<parameter name="city">城市名</parameter>
</invoke>
</function_calls>"""
    
    async with client.messages.stream(
        model="claude-3-opus-20240229",
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": "北京和上海的天气怎么样？"}]
    ) as stream:
        async for chunk in stream.text_stream:
            print(chunk, end="", flush=True)
            
            # 实时解析工具调用
            for tool_call in parser.parse_chunk(chunk):
                print(f"\n[检测到工具调用: {tool_call['tool_name']}]")
                
                # 立即执行工具
                result = await execute_tool(tool_call)
                print(f"[工具结果: {result}]")
                
                # 可以选择将结果注入到后续对话中
                # 或者等待所有工具执行完成后统一处理

# 运行流式处理
asyncio.run(stream_with_tools())
```

### cURL 示例

```bash
# Anthropic API 请求
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-3-opus-20240229",
    "max_tokens": 1024,
    "system": "你是一个有用的助手。当需要获取天气信息时，使用以下格式调用工具：\n<function_calls>\n<invoke name=\"get_weather\">\n<parameter name=\"city\">城市名</parameter>\n</invoke>\n</function_calls>",
    "messages": [
      {"role": "user", "content": "北京今天天气怎么样？"}
    ]
  }'

# 响应示例
{
  "content": [{
    "type": "text",
    "text": "我来帮您查询北京的天气情况。\n\n<function_calls>\n<invoke name=\"get_weather\">\n<parameter name=\"city\">北京</parameter>\n<parameter name=\"unit\">celsius</parameter>\n</invoke>\n</function_calls>\n\n请稍等，我正在获取天气信息..."
  }]
}

# 发送工具执行结果
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-3-opus-20240229",
    "max_tokens": 1024,
    "system": "你是一个有用的助手。当需要获取天气信息时，使用工具调用格式。",
    "messages": [
      {"role": "user", "content": "北京今天天气怎么样？"},
      {"role": "assistant", "content": "我来帮您查询北京的天气情况。\n\n<function_calls>\n<invoke name=\"get_weather\">\n<parameter name=\"city\">北京</parameter>\n</invoke>\n</function_calls>"},
      {"role": "user", "content": "<result>{\"temperature\": 25, \"description\": \"晴朗\", \"humidity\": 60}</result>"}
    ]
  }'
```

### 高级 XML 解析器

```python
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

class AdvancedXMLToolParser:
    """更健壮的 XML 工具解析器"""
    
    def parse_content(self, content: str) -> List[Dict[str, Any]]:
        """从内容中解析所有工具调用"""
        tool_calls = []
        
        # 查找所有 function_calls 块
        import re
        pattern = r'<function_calls>(.*?)</function_calls>'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                # 包装成完整的 XML 以便解析
                xml_content = f"<root>{match}</root>"
                root = ET.fromstring(xml_content)
                
                # 查找所有 invoke 元素
                for invoke in root.findall('.//invoke'):
                    tool_name = invoke.get('name')
                    if not tool_name:
                        continue
                    
                    # 解析参数
                    parameters = {}
                    
                    # 解析子元素作为参数
                    for param in invoke:
                        if param.tag == 'parameter':
                            param_name = param.get('name')
                            param_value = param.text
                            if param_name and param_value:
                                parameters[param_name] = param_value.strip()
                    
                    tool_calls.append({
                        'name': tool_name,
                        'parameters': parameters,
                        'raw_xml': ET.tostring(invoke, encoding='unicode')
                    })
                    
            except ET.ParseError as e:
                print(f"XML 解析错误: {e}")
                # 可以回退到正则表达式解析
                continue
        
        return tool_calls

# 使用示例
parser = AdvancedXMLToolParser()
content = """
让我帮您查询多个城市的天气。

<function_calls>
<invoke name="get_weather">
<parameter name="city">北京</parameter>
<parameter name="unit">celsius</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="get_weather">
<parameter name="city">上海</parameter>
<parameter name="unit">celsius</parameter>
</invoke>
</function_calls>
"""

tool_calls = parser.parse_content(content)
for call in tool_calls:
    print(f"工具: {call['name']}, 参数: {call['parameters']}")
```

## 关键区别总结

### 1. 请求格式

| 特性 | OpenAI | Anthropic |
|------|--------|-----------|
| 工具定义位置 | `tools` 参数 | `system` 提示 |
| 工具定义格式 | JSON Schema | 文本描述或 XML |
| 工具选择控制 | `tool_choice` 参数 | 提示工程 |

### 2. 响应处理

| 特性 | OpenAI | Anthropic |
|------|--------|-----------|
| 工具调用格式 | 结构化 `tool_calls` 对象 | 嵌入在文本中的 XML |
| 解析方式 | 直接访问对象属性 | 需要解析 XML/正则匹配 |
| 多工具调用 | 数组形式 | 多个 XML 块 |

### 3. 对话流程

| 特性 | OpenAI | Anthropic |
|------|--------|-----------|
| 往返次数 | 至少 2 次（调用→结果→回复） | 可以单次完成 |
| 结果返回 | 独立的 `tool` 角色消息 | 用户消息或继续助手消息 |
| 上下文保持 | 通过消息历史 | 自然的对话流 |

### 4. 流式处理

| 特性 | OpenAI | Anthropic |
|------|--------|-----------|
| 工具检测时机 | 流结束时 | 实时检测 |
| 执行时机 | 接收完整响应后 | 可以立即执行 |
| 复杂度 | 较低 | 需要流式 XML 解析 |

## 在 Suna 中的使用

Suna 通过统一的抽象层支持这两种格式，开发者可以：

### 1. 定义一次，支持两种格式

```python
from suna import Tool, openapi_schema, xml_schema

class WeatherTool(Tool):
    @openapi_schema(
        description="获取天气信息",
        city="城市名称",
        unit="温度单位"
    )
    @xml_schema(
        name="get_weather",
        elements=["city", "unit"]
    )
    def get_weather(self, city: str, unit: str = "celsius"):
        # 实现逻辑
        return {"temperature": 25, "description": "晴朗"}
```

### 2. 自动格式转换

```python
# Suna 会根据使用的 LLM 自动选择合适的格式
agent = Agent(
    model="gpt-4",  # 自动使用 OpenAI 格式
    tools=[WeatherTool()]
)

agent2 = Agent(
    model="claude-3",  # 自动使用 XML 格式
    tools=[WeatherTool()]
)
```

### 3. 统一的响应处理

```python
# 无论使用哪种格式，Suna 都提供统一的接口
response = await agent.chat("北京天气怎么样？")
# Suna 自动处理工具调用和结果集成
```

这种设计让开发者能够：
- 轻松切换不同的 LLM 提供商
- 重用相同的工具定义
- 获得一致的开发体验
- 根据需求选择最优的格式

## 最佳实践

1. **选择合适的格式**：
   - 如果需要严格的类型检查和标准化，选择 OpenAI 格式
   - 如果需要更自然的对话流和实时处理，选择 Anthropic 格式

2. **错误处理**：
   - OpenAI 格式：处理 JSON 解析错误和 API 错误
   - Anthropic 格式：处理 XML 解析错误和格式不匹配

3. **性能优化**：
   - 批量处理多个工具调用
   - 使用异步执行提高并发性
   - 实现结果缓存减少重复调用

4. **安全考虑**：
   - 验证所有工具参数
   - 限制工具执行权限
   - 记录所有工具调用日志

## 完整的生产环境示例

### OpenAI 格式的生产级实现

```python
import openai
import json
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ToolError(Exception):
    """工具执行错误"""
    pass

@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: callable

class OpenAIToolExecutor:
    """OpenAI 工具执行器"""
    
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.tools: Dict[str, ToolDefinition] = {}
        
    def register_tool(self, tool_def: ToolDefinition):
        """注册工具"""
        self.tools[tool_def.name] = tool_def
        logger.info(f"注册工具: {tool_def.name}")
        
    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """获取 OpenAI 格式的工具定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in self.tools.values()
        ]
    
    async def execute_tool(self, tool_call) -> Dict[str, Any]:
        """执行工具调用"""
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        logger.info(f"执行工具: {function_name}, 参数: {function_args}")
        
        if function_name not in self.tools:
            raise ToolError(f"未知工具: {function_name}")
        
        tool = self.tools[function_name]
        try:
            # 执行工具处理函数
            result = await tool.handler(**function_args)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def chat_with_tools(self, messages: List[Dict[str, str]], model: str = "gpt-4"):
        """带工具的对话"""
        try:
            # 第一次调用 - 可能包含工具调用
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=self.get_openai_tools(),
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            
            # 如果没有工具调用，直接返回
            if not message.tool_calls:
                return message.content
            
            # 处理工具调用
            messages.append(message)  # 添加助手的响应
            
            # 并行执行所有工具
            tool_results = []
            for tool_call in message.tool_calls:
                result = await self.execute_tool(tool_call)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })
                messages.append(tool_results[-1])
            
            # 第二次调用 - 基于工具结果生成最终回复
            final_response = self.client.chat.completions.create(
                model=model,
                messages=messages
            )
            
            return final_response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"对话失败: {e}")
            raise

# 使用示例
async def main():
    executor = OpenAIToolExecutor(api_key="your-api-key")
    
    # 注册工具
    async def get_weather(city: str, unit: str = "celsius"):
        # 实际的天气 API 调用
        return {"temperature": 25, "description": "晴朗", "city": city}
    
    executor.register_tool(ToolDefinition(
        name="get_weather",
        description="获取天气信息",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["city"]
        },
        handler=get_weather
    ))
    
    # 进行对话
    messages = [{"role": "user", "content": "北京和上海的天气怎么样？"}]
    response = await executor.chat_with_tools(messages)
    print(response)

# 运行
import asyncio
asyncio.run(main())
```

### Anthropic 格式的生产级实现

```python
import anthropic
import re
import asyncio
from typing import Dict, Any, List, AsyncGenerator
from dataclasses import dataclass
import xml.etree.ElementTree as ET

@dataclass
class XMLTool:
    """XML 工具定义"""
    name: str
    description: str
    parameters: List[Dict[str, str]]
    handler: callable

class AnthropicXMLToolExecutor:
    """Anthropic XML 工具执行器"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.async_client = anthropic.AsyncAnthropic(api_key=api_key)
        self.tools: Dict[str, XMLTool] = {}
        self.execution_results: Dict[str, Any] = {}
        
    def register_tool(self, tool: XMLTool):
        """注册工具"""
        self.tools[tool.name] = tool
        
    def generate_system_prompt(self) -> str:
        """生成包含工具说明的系统提示"""
        tools_desc = []
        for tool in self.tools.values():
            params_desc = []
            for param in tool.parameters:
                required = "required" if param.get("required", False) else "optional"
                params_desc.append(
                    f'    <parameter name="{param["name"]}" type="{param["type"]}" {required}>'
                    f'{param["description"]}</parameter>'
                )
            
            tools_desc.append(f"""
<tool name="{tool.name}">
  <description>{tool.description}</description>
  <parameters>
{chr(10).join(params_desc)}
  </parameters>
</tool>""")
        
        return f"""你是一个有用的助手。你可以使用以下工具：

<tools>
{''.join(tools_desc)}
</tools>

当你需要调用工具时，请使用以下格式：
<function_calls>
<invoke name="tool_name">
<parameter name="param_name">param_value</parameter>
</invoke>
</function_calls>

你可以在一次回复中调用多个工具。工具执行后，结果会以 <result> 标签返回给你。"""
    
    async def parse_and_execute_tools(self, content: str) -> List[Dict[str, Any]]:
        """解析并执行内容中的所有工具调用"""
        results = []
        
        # 查找所有工具调用
        pattern = r'<function_calls>\s*<invoke\s+name="([^"]+)">(.*?)</invoke>\s*</function_calls>'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for tool_name, params_xml in matches:
            if tool_name not in self.tools:
                results.append({
                    "tool": tool_name,
                    "error": f"未知工具: {tool_name}"
                })
                continue
            
            # 解析参数
            params = {}
            param_pattern = r'<parameter\s+name="([^"]+)">([^<]*)</parameter>'
            param_matches = re.findall(param_pattern, params_xml)
            
            for param_name, param_value in param_matches:
                params[param_name] = param_value.strip()
            
            # 执行工具
            tool = self.tools[tool_name]
            try:
                result = await tool.handler(**params)
                results.append({
                    "tool": tool_name,
                    "params": params,
                    "result": result
                })
            except Exception as e:
                results.append({
                    "tool": tool_name,
                    "params": params,
                    "error": str(e)
                })
        
        return results
    
    async def stream_with_tools(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "claude-3-opus-20240229"
    ) -> AsyncGenerator[str, None]:
        """流式处理带工具的对话"""
        system_prompt = self.generate_system_prompt()
        
        # 创建流式会话
        async with self.async_client.messages.stream(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=messages
        ) as stream:
            
            buffer = ""
            async for chunk in stream.text_stream:
                buffer += chunk
                yield chunk  # 实时输出文本
                
                # 检查是否有完整的工具调用
                if '</function_calls>' in buffer:
                    # 执行检测到的工具
                    tool_results = await self.parse_and_execute_tools(buffer)
                    
                    if tool_results:
                        # 生成结果文本
                        result_text = "\n\n"
                        for result in tool_results:
                            if "error" in result:
                                result_text += f"<result tool=\"{result['tool']}\" status=\"error\">\n{result['error']}\n</result>\n"
                            else:
                                result_text += f"<result tool=\"{result['tool']}\" status=\"success\">\n{json.dumps(result['result'], ensure_ascii=False)}\n</result>\n"
                        
                        yield result_text
                        
                        # 清空已处理的工具调用
                        pattern = r'<function_calls>.*?</function_calls>'
                        buffer = re.sub(pattern, '', buffer, flags=re.DOTALL)
    
    async def chat_with_tools(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "claude-3-opus-20240229",
        stream: bool = False
    ):
        """带工具的对话"""
        if stream:
            return self.stream_with_tools(messages, model)
        
        system_prompt = self.generate_system_prompt()
        
        # 非流式处理
        response = await self.async_client.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=messages
        )
        
        content = response.content[0].text
        
        # 解析并执行工具
        tool_results = await self.parse_and_execute_tools(content)
        
        if not tool_results:
            return content
        
        # 构建包含结果的消息
        messages.append({"role": "assistant", "content": content})
        
        result_content = ""
        for result in tool_results:
            if "error" in result:
                result_content += f"<result tool=\"{result['tool']}\" status=\"error\">{result['error']}</result>\n"
            else:
                result_content += f"<result tool=\"{result['tool']}\" status=\"success\">{json.dumps(result['result'], ensure_ascii=False)}</result>\n"
        
        messages.append({"role": "user", "content": result_content})
        
        # 获取最终回复
        final_response = await self.async_client.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=messages
        )
        
        return final_response.content[0].text

# 使用示例
async def main():
    executor = AnthropicXMLToolExecutor(api_key="your-api-key")
    
    # 注册工具
    async def get_weather(city: str, unit: str = "celsius"):
        # 模拟 API 调用
        await asyncio.sleep(1)  # 模拟网络延迟
        return {
            "city": city,
            "temperature": 25,
            "description": "晴朗",
            "unit": unit
        }
    
    executor.register_tool(XMLTool(
        name="get_weather",
        description="获取城市天气信息",
        parameters=[
            {"name": "city", "type": "string", "description": "城市名称", "required": True},
            {"name": "unit", "type": "string", "description": "温度单位", "required": False}
        ],
        handler=get_weather
    ))
    
    # 流式对话
    messages = [{"role": "user", "content": "告诉我北京和上海的天气"}]
    
    print("=== 流式响应 ===")
    async for chunk in executor.chat_with_tools(messages, stream=True):
        print(chunk, end="", flush=True)
    
    print("\n\n=== 非流式响应 ===")
    response = await executor.chat_with_tools(messages, stream=False)
    print(response)

# 运行
asyncio.run(main())
```

## 错误处理和重试机制

### OpenAI 格式的错误处理

```python
import openai
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

class RobustOpenAIExecutor:
    """带有错误处理和重试的 OpenAI 执行器"""
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def call_with_retry(self, **kwargs):
        """带重试的 API 调用"""
        try:
            return await self.client.chat.completions.create(**kwargs)
        except openai.APIError as e:
            logging.error(f"API 错误: {e}")
            raise
        except openai.APIConnectionError as e:
            logging.error(f"连接错误: {e}")
            raise
        except openai.RateLimitError as e:
            logging.error(f"速率限制: {e}")
            raise
    
    async def execute_with_fallback(self, tool_call, primary_handler, fallback_handler):
        """带降级的工具执行"""
        try:
            return await primary_handler(tool_call)
        except Exception as e:
            logging.warning(f"主处理器失败，使用降级: {e}")
            return await fallback_handler(tool_call)
```

### Anthropic 格式的错误处理

```python
class RobustAnthropicExecutor:
    """带有错误处理的 Anthropic 执行器"""
    
    def parse_with_fallback(self, content: str) -> List[Dict[str, Any]]:
        """带降级的 XML 解析"""
        try:
            # 首先尝试严格的 XML 解析
            return self.strict_xml_parse(content)
        except ET.ParseError:
            # 降级到正则表达式解析
            logging.warning("XML 解析失败，使用正则表达式")
            return self.regex_parse(content)
    
    def validate_tool_params(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """验证和清理工具参数"""
        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"未知工具: {tool_name}")
        
        cleaned_params = {}
        for param_def in tool.parameters:
            param_name = param_def["name"]
            param_type = param_def["type"]
            required = param_def.get("required", False)
            
            if param_name in params:
                # 类型转换和验证
                value = params[param_name]
                if param_type == "integer":
                    cleaned_params[param_name] = int(value)
                elif param_type == "float":
                    cleaned_params[param_name] = float(value)
                elif param_type == "boolean":
                    cleaned_params[param_name] = value.lower() in ("true", "yes", "1")
                else:
                    cleaned_params[param_name] = str(value)
            elif required:
                raise ValueError(f"缺少必需参数: {param_name}")
        
        return cleaned_params
```

## 性能优化建议

### 1. 连接池管理

```python
import aiohttp
from aiohttp import ClientSession

class ConnectionPoolManager:
    """连接池管理器"""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        
    async def get_session(self) -> ClientSession:
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=100,  # 总连接数限制
                limit_per_host=30,  # 每个主机的连接数限制
                ttl_dns_cache=300  # DNS 缓存时间
            )
            self.session = ClientSession(connector=connector)
        return self.session
    
    async def close(self):
        if self.session:
            await self.session.close()
```

### 2. 批量工具执行

```python
async def batch_execute_tools(tool_calls: List[ToolCall], max_concurrent: int = 5):
    """批量执行工具，控制并发数"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute_with_limit(tool_call):
        async with semaphore:
            return await execute_tool(tool_call)
    
    tasks = [execute_with_limit(tc) for tc in tool_calls]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### 3. 结果缓存

```python
from functools import lru_cache
import hashlib
import json

class ToolResultCache:
    """工具结果缓存"""
    
    def __init__(self, max_size: int = 1000):
        self.cache = {}
        self.max_size = max_size
        
    def get_cache_key(self, tool_name: str, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(f"{tool_name}:{param_str}".encode()).hexdigest()
    
    async def get_or_execute(self, tool_name: str, params: Dict[str, Any], executor):
        """从缓存获取或执行"""
        cache_key = self.get_cache_key(tool_name, params)
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        result = await executor(tool_name, params)
        
        # 限制缓存大小
        if len(self.cache) >= self.max_size:
            # 简单的 FIFO 策略
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[cache_key] = result
        return result
```