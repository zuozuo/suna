# 双模态工具调用系统深度分析

## 概述

本文档详细分析了系统中如何实现同时支持 OpenAPI 和 XML 两种工具调用格式的机制。通过装饰器模式和灵活的注册系统，同一个工具方法可以根据 LLM 的需求，以不同的格式被调用。

## 1. 装饰器实现机制

### 1.1 Python 方法属性基础

在 Python 中，函数是一等对象，可以像普通对象一样添加属性：

```python
def my_function():
    return "Hello"

# 给函数添加属性
my_function.author = "Alice"
my_function.version = "1.0"
my_function.metadata = {"created": "2024-01-01"}

print(my_function.author)  # 输出: Alice
```

### 1.2 装饰器添加属性

使用装饰器是更优雅的方式：

```python
def add_metadata(**kwargs):
    def decorator(func):
        for key, value in kwargs.items():
            setattr(func, key, value)
        return func
    return decorator

@add_metadata(author="Bob", version="2.0")
def process_data():
    return "Processing..."

print(process_data.author)  # 输出: Bob
```

### 1.3 链式装饰器

多个装饰器可以链式使用，每个装饰器都可以添加自己的属性：

```python
def openapi_schema(**schema_data):
    def decorator(func):
        if not hasattr(func, 'tool_schemas'):
            func.tool_schemas = []
        func.tool_schemas.append({
            'type': 'openapi',
            'data': schema_data
        })
        return func
    return decorator

def xml_schema(**schema_data):
    def decorator(func):
        if not hasattr(func, 'tool_schemas'):
            func.tool_schemas = []
        func.tool_schemas.append({
            'type': 'xml',
            'data': schema_data
        })
        return func
    return decorator

# 使用多个装饰器
@openapi_schema(description="创建文件")
@xml_schema(name="create-file", elements=["content"])
def create_file(content):
    return f"File created with: {content}"

print(create_file.tool_schemas)
# 输出: [{'type': 'xml', 'data': {...}}, {'type': 'openapi', 'data': {...}}]
```

## 2. 实际代码示例

### 2.1 工具方法定义

以 `SandboxFilesTool` 中的 `str_replace_editor` 方法为例：

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

## 3. 装饰器工作原理

### 3.1 装饰器定义

两个装饰器都通过 `_add_schema` 函数将 schema 信息附加到方法上：

```python
def _add_schema(func, schema: ToolSchema):
    """将 schema 添加到函数"""
    if not hasattr(func, 'tool_schemas'):
        func.tool_schemas = []
    func.tool_schemas.append(schema)
    return func
```

### 3.2 Schema 收集

工具基类在初始化时收集所有带装饰器的方法：

```python
def _register_schemas(self):
    """从所有装饰的方法注册 schemas"""
    for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
        if hasattr(method, 'tool_schemas'):
            self._schemas[name] = method.tool_schemas
```

## 4. 工具注册流程

### 4.1 注册入口

在 `run.py` 中注册工具：

```python
# 注册工具到 ThreadManager
thread_manager.add_tool(MessageTool)
thread_manager.add_tool(SandboxWebSearchTool, project_id=project_id, thread_manager=thread_manager)

# ThreadManager.add_tool 内部调用 ToolRegistry.register_tool
def add_tool(self, tool_class: Type[Tool], function_names: Optional[List[str]] = None, **kwargs):
    self.tool_registry.register_tool(tool_class, function_names, **kwargs)
```

### 4.2 核心注册逻辑

在 `ToolRegistry.register_tool()` 中实现双重注册：

```python
def register_tool(self, tool_class: Type[Tool], function_names: Optional[List[str]] = None, **kwargs):
    """注册工具，支持选择性函数过滤"""
    # 实例化工具
    tool_instance = tool_class(**kwargs)
    
    # 获取工具的所有 schemas
    schemas = tool_instance.get_schemas()
    
    # 遍历每个方法的 schemas
    for func_name, schema_list in schemas.items():
        if function_names is None or func_name in function_names:
            # 每个方法可能有多个 schema（OpenAPI 和 XML）
            for schema in schema_list:
                # OpenAPI 注册
                if schema.schema_type == SchemaType.OPENAPI:
                    self.tools[func_name] = {
                        "instance": tool_instance,
                        "schema": schema
                    }
                
                # XML 注册
                if schema.schema_type == SchemaType.XML and schema.xml_schema:
                    self.xml_tools[schema.xml_schema.tag_name] = {
                        "instance": tool_instance,
                        "method": func_name,
                        "schema": schema
                    }
```

### 4.3 同一方法的双重注册

对于 `str_replace_editor` 方法：

```python
# 方法的 schemas 结构
schemas = {
    "str_replace_editor": [
        ToolSchema(schema_type=OPENAPI, ...),
        ToolSchema(schema_type=XML, ...)
    ]
}

# 注册后的存储结构
# OpenAPI 注册：通过函数名 "str_replace_editor" 注册
self.tools["str_replace_editor"] = {
    "instance": <SandboxFilesTool instance>,
    "schema": <OpenAPI ToolSchema>
}

# XML 注册：通过标签名 "str_replace_editor" 注册
self.xml_tools["str_replace_editor"] = {
    "instance": <SandboxFilesTool instance>,
    "method": "str_replace_editor",
    "schema": <XML ToolSchema>
}
```

## 5. 存储结构详解

### 5.1 ToolRegistry 数据结构

```python
class ToolRegistry:
    def __init__(self):
        # OpenAPI 格式的工具存储
        self.tools = {}        # key: 函数名, value: {instance, schema}
        
        # XML 格式的工具存储
        self.xml_tools = {}    # key: XML标签名, value: {instance, method, schema}
```

### 5.2 OpenAPI 存储格式

```python
self.tools = {
    "str_replace_editor": {
        "instance": tool_instance,  # 工具实例
        "schema": schema           # OpenAPI schema
    }
}
```

### 5.3 XML 存储格式

```python
self.xml_tools = {
    "str_replace_editor": {
        "instance": tool_instance,  # 工具实例
        "method": "str_replace_editor",  # 对应的方法名
        "schema": schema          # 包含 XML schema 信息
    }
}
```

## 6. 调用路径分析

### 6.1 OpenAPI 调用路径

当 LLM 返回 OpenAPI 格式的函数调用时：

```python
# LLM 返回
{
    "function": {
        "name": "str_replace_editor",
        "arguments": {
            "command": "str_replace",
            "path": "/path/to/file",
            "old_str": "old text",
            "new_str": "new text"
        }
    }
}

# 处理流程
tool_info = registry.tools["str_replace_editor"]
result = await tool_info["instance"].str_replace_editor(**arguments)
```

### 6.2 XML 调用路径

当 LLM 返回 XML 格式的工具调用时：

```python
# LLM 返回
<str_replace_editor command="str_replace" path="/path/to/file">
    <old_str>old text</old_str>
    <new_str>new text</new_str>
</str_replace_editor>

# 处理流程
xml_info = registry.xml_tools["str_replace_editor"]
method = getattr(xml_info["instance"], xml_info["method"])
result = await method(**parsed_args)
```

## 7. 参数映射机制

### 7.1 OpenAPI 参数映射

OpenAPI 格式直接使用 JSON 参数，无需特殊映射。

### 7.2 XML 参数映射

XML 格式支持多种映射方式：

```python
@xml_schema(
    name="str_replace_editor",
    attributes=["command", "path"],      # 从属性获取
    elements=["old_str", "new_str"]      # 从子元素获取
)
```

更复杂的映射示例：

```python
@xml_schema(
    tag_name="ask",
    mappings=[
        {"param_name": "text", "node_type": "content", "path": "."},
        {"param_name": "attachments", "node_type": "attribute", "path": ".", "required": False}
    ]
)
```

## 8. 检索机制

### 8.1 获取可用工具

```python
# 获取所有 OpenAPI 工具
def get_openapi_schemas(self):
    return [info["schema"] for info in self.tools.values()]

# 获取所有 XML 示例
def get_xml_examples(self):
    examples = []
    for xml_info in self.xml_tools.values():
        if xml_info["schema"].xml_schema and xml_info["schema"].xml_schema.example:
            examples.append(xml_info["schema"].xml_schema.example)
    return examples
```

### 8.2 工具查找

```python
# OpenAPI 工具查找
tool_info = self.tools.get("str_replace_editor")

# XML 工具查找
xml_tool_info = self.xml_tools.get("str_replace_editor")
```

## 9. 系统优势

### 9.1 解耦性

- 工具实现与调用格式解耦
- 开发者只需关注业务逻辑
- 框架负责处理不同格式的转换

### 9.2 灵活性

- 同一工具支持多种调用方式
- LLM 可根据偏好选择格式
- 易于扩展新的调用格式

### 9.3 维护性

- 统一的工具实现
- 避免重复代码
- 清晰的职责分离

## 10. 完整工作流程

1. **定义阶段**：使用 `@openapi_schema` 和 `@xml_schema` 装饰工具方法
2. **收集阶段**：工具基类初始化时收集所有带装饰器的方法
3. **注册阶段**：`ToolRegistry` 根据 schema 类型分别注册到不同存储
4. **调用阶段**：`ResponseProcessor` 解析 LLM 响应，识别格式并路由到对应工具
5. **执行阶段**：最终都调用同一个底层方法实现

## 11. 关键设计决策

### 11.1 为什么使用装饰器？

- 声明式编程，代码更清晰
- 元数据与实现分离
- 支持多个装饰器组合

### 11.2 为什么分开存储？

- OpenAPI 和 XML 有不同的查找键（函数名 vs 标签名）
- 避免命名冲突
- 提高查找效率

### 11.3 为什么共享实例？

- 避免重复实例化
- 共享状态和资源
- 保证行为一致性

## 总结

通过装饰器模式和灵活的注册机制，系统实现了：

1. **一次实现，多种调用**：开发者只需实现一次业务逻辑
2. **格式无关**：工具实现不依赖特定的调用格式
3. **易于扩展**：可以轻松添加新的调用格式支持
4. **类型安全**：保持了 Python 的类型提示和参数验证

这种设计为系统提供了极大的灵活性，使得不同的 LLM 可以根据自己的能力和偏好选择合适的工具调用格式。