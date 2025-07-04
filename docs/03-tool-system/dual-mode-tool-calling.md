# 双模态工具调用系统实现分析

## 概述

AgentPress 框架通过 `openapi_schema` 和 `xml_schema` 两个装饰器实现了双模态工具调用系统，允许同一个工具方法同时支持两种不同的调用格式：
- **OpenAPI 格式**：符合 OpenAI Function Calling 标准的 JSON 格式
- **XML 格式**：基于 XML 标签的调用格式（类似 Claude 的工具调用风格）

## 核心组件

### 1. 装饰器定义（agentpress/tool.py）

#### openapi_schema 装饰器
```python
def openapi_schema(schema: Dict[str, Any]):
    """Decorator for OpenAPI schema tools."""
    def decorator(func):
        return _add_schema(func, ToolSchema(
            schema_type=SchemaType.OPENAPI,
            schema=schema
        ))
    return decorator
```

#### xml_schema 装饰器
```python
def xml_schema(
    tag_name: str,
    mappings: List[Dict[str, Any]] = None,
    example: str = None
):
    """Decorator for XML schema tools with improved node mapping."""
    def decorator(func):
        xml_schema = XMLTagSchema(tag_name=tag_name, example=example)
        
        # Add mappings
        if mappings:
            for mapping in mappings:
                xml_schema.add_mapping(
                    param_name=mapping["param_name"],
                    node_type=mapping.get("node_type", "element"),
                    path=mapping.get("path", "."),
                    required=mapping.get("required", True)
                )
                
        return _add_schema(func, ToolSchema(
            schema_type=SchemaType.XML,
            schema={},
            xml_schema=xml_schema
        ))
    return decorator
```

### 2. 工具示例（agent/tools/sb_files_tool.py）

一个方法可以同时使用两个装饰器：

```python
@openapi_schema({
    "type": "function",
    "function": {
        "name": "create_file",
        "description": "Create a new file with the provided contents",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "file_contents": {"type": "string"},
                "permissions": {"type": "string", "default": "644"}
            },
            "required": ["file_path", "file_contents"]
        }
    }
})
@xml_schema(
    tag_name="create-file",
    mappings=[
        {"param_name": "file_path", "node_type": "attribute", "path": "."},
        {"param_name": "file_contents", "node_type": "content", "path": "."}
    ],
    example='''
    <function_calls>
    <invoke name="create_file">
    <parameter name="file_path">src/main.py</parameter>
    <parameter name="file_contents">
    # This is the file content
    def main():
        print("Hello, World!")
    </parameter>
    </invoke>
    </function_calls>
    '''
)
async def create_file(self, file_path: str, file_contents: str, permissions: str = "644") -> ToolResult:
    # 方法实现
    pass
```

## 工作流程

### 1. 工具注册阶段

当工具类被实例化时，`Tool` 基类的构造函数会自动收集所有带有装饰器的方法：

```python
class Tool(ABC):
    def __init__(self):
        self._schemas: Dict[str, List[ToolSchema]] = {}
        self._register_schemas()

    def _register_schemas(self):
        """Register schemas from all decorated methods."""
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, 'tool_schemas'):
                self._schemas[name] = method.tool_schemas
```

### 2. 工具注册到 Registry

`ToolRegistry` 负责管理所有工具，并根据 schema 类型进行分类存储：

```python
def register_tool(self, tool_class: Type[Tool], function_names: Optional[List[str]] = None, **kwargs):
    tool_instance = tool_class(**kwargs)
    schemas = tool_instance.get_schemas()
    
    for func_name, schema_list in schemas.items():
        if function_names is None or func_name in function_names:
            for schema in schema_list:
                if schema.schema_type == SchemaType.OPENAPI:
                    self.tools[func_name] = {
                        "instance": tool_instance,
                        "schema": schema
                    }
                
                if schema.schema_type == SchemaType.XML and schema.xml_schema:
                    self.xml_tools[schema.xml_schema.tag_name] = {
                        "instance": tool_instance,
                        "method": func_name,
                        "schema": schema
                    }
```

关键点：
- OpenAPI 工具通过**函数名**索引
- XML 工具通过**XML 标签名**索引
- 同一个方法可以同时注册到两个索引中

### 3. 工具调用阶段

#### OpenAPI 格式调用
当 LLM 返回 OpenAI 格式的工具调用时：
```json
{
    "tool_calls": [{
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "create_file",
            "arguments": "{\"file_path\": \"test.py\", \"file_contents\": \"print('hello')\"}"
        }
    }]
}
```

#### XML 格式调用
当 LLM 返回 XML 格式的工具调用时：
```xml
<function_calls>
<invoke name="create_file">
<parameter name="file_path">test.py</parameter>
<parameter name="file_contents">print('hello')</parameter>
</invoke>
</function_calls>
```

### 4. 工具执行

`ResponseProcessor` 中的 `_execute_tool` 方法负责实际执行：

```python
async def _execute_tool(self, tool_call: Dict[str, Any]) -> ToolResult:
    function_name = tool_call["function_name"]
    arguments = tool_call["arguments"]
    
    # 从 registry 获取可用函数
    available_functions = self.tool_registry.get_available_functions()
    
    # 查找函数
    tool_fn = available_functions.get(function_name)
    if not tool_fn:
        return ToolResult(success=False, output=f"Tool function '{function_name}' not found")
    
    # 执行函数
    result = await tool_fn(**arguments)
    return result
```

## XML 参数映射机制

XML schema 支持多种参数映射类型：

### 1. 属性映射（attribute）
```xml
<create-file file_path="test.py">
```
映射配置：
```python
{"param_name": "file_path", "node_type": "attribute", "path": "."}
```

### 2. 元素映射（element）
```xml
<old_str>text to replace</old_str>
```
映射配置：
```python
{"param_name": "old_str", "node_type": "element", "path": "old_str"}
```

### 3. 内容映射（content）
```xml
<create-file>
    This is the content
</create-file>
```
映射配置：
```python
{"param_name": "file_contents", "node_type": "content", "path": "."}
```

## 关键设计优势

1. **解耦性**：工具实现与调用格式完全解耦，方法本身不需要知道是通过哪种格式被调用的

2. **灵活性**：可以根据不同的 LLM 提供不同的调用格式，同时保持相同的底层实现

3. **扩展性**：可以轻松添加新的 schema 类型（如 `custom_schema`）

4. **向后兼容**：支持旧版 XML 格式的同时，也支持新的标准化格式

5. **统一接口**：无论使用哪种格式，最终都通过相同的 `ToolResult` 返回结果

## 实际应用场景

这种双模态设计特别适合以下场景：

1. **多 LLM 支持**：不同的 LLM 可能偏好不同的工具调用格式
2. **渐进式迁移**：从一种格式迁移到另一种格式时，可以同时支持两种
3. **用户偏好**：允许用户选择他们熟悉的调用格式
4. **性能优化**：某些格式可能在特定场景下有更好的性能表现

## 总结

通过装饰器模式和注册表机制，AgentPress 实现了一个优雅的双模态工具调用系统。这种设计不仅提供了极大的灵活性，还保持了代码的清晰和可维护性。工具开发者只需要专注于实现业务逻辑，而框架负责处理不同的调用格式转换。