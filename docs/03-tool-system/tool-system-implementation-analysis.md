# Suna 工具系统实现分析

## 概述

本文档深入分析了 Suna 项目中的工具系统实现，包括工具注册机制、装饰器使用、参数验证、错误处理以及前端展示机制，并提供了创建自定义工具的完整流程和最佳实践。

## 1. 工具系统架构

### 1.1 核心组件

#### Tool 基类 (`agentpress/tool.py`)
- 所有工具必须继承的抽象基类
- 提供统一的结果处理方法（`success_response`、`fail_response`）
- 自动注册带有装饰器的方法

```python
class Tool(ABC):
    def __init__(self):
        self._schemas: Dict[str, List[ToolSchema]] = {}
        self._register_schemas()
    
    def success_response(self, data: Union[Dict[str, Any], str]) -> ToolResult:
        """创建成功结果"""
        
    def fail_response(self, msg: str) -> ToolResult:
        """创建失败结果"""
```

#### Schema 装饰器
支持两种模式定义：

1. **OpenAPI Schema**
```python
@openapi_schema({
    "type": "function",
    "function": {
        "name": "function_name",
        "description": "功能描述",
        "parameters": {...}
    }
})
```

2. **XML Schema**
```python
@xml_schema(
    tag_name="function-name",
    mappings=[...],
    example="..."
)
```

#### ToolRegistry (`agentpress/tool_registry.py`)
- 管理和访问工具的中央注册表
- 支持选择性注册工具函数
- 同时处理 OpenAPI 和 XML 模式

```python
class ToolRegistry:
    def register_tool(self, tool_class: Type[Tool], function_names: Optional[List[str]] = None, **kwargs):
        """注册工具及其函数"""
    
    def get_tool(self, tool_name: str) -> Dict[str, Any]:
        """获取特定工具"""
    
    def get_openapi_schemas(self) -> List[Dict[str, Any]]:
        """获取所有 OpenAPI schemas"""
```

### 1.2 工具注册流程

1. **ThreadManager 初始化**
   ```python
   thread_manager = ThreadManager(trace=trace, ...)
   ```

2. **添加工具**
   ```python
   thread_manager.add_tool(ToolClass, param1=value1, param2=value2)
   ```

3. **内部流程**
   - `ThreadManager.add_tool` → `ToolRegistry.register_tool`
   - 创建工具实例并获取其 schemas
   - 根据 schema 类型注册到相应的字典中

## 2. 创建自定义工具完整流程

### 2.1 基础工具模板

```python
from typing import Optional
from agentpress.tool import Tool, ToolResult, openapi_schema, xml_schema
from utils.logger import logger

class MyCustomTool(Tool):
    """自定义工具的简要描述"""
    
    def __init__(self, config_param: str = "default"):
        """初始化工具
        
        Args:
            config_param: 配置参数示例
        """
        super().__init__()
        self.config = config_param
        logger.info(f"初始化 MyCustomTool，配置: {config_param}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "process_data",
            "description": "处理数据并返回结果。支持多种数据格式和处理选项。",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "要处理的数据内容"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "text", "csv"],
                        "description": "数据格式",
                        "default": "text"
                    },
                    "options": {
                        "type": "object",
                        "description": "额外的处理选项",
                        "properties": {
                            "validate": {
                                "type": "boolean",
                                "description": "是否验证数据",
                                "default": true
                            }
                        }
                    }
                },
                "required": ["data"]
            }
        }
    })
    @xml_schema(
        tag_name="process-data",
        mappings=[
            {"param_name": "data", "node_type": "content", "path": "."},
            {"param_name": "format", "node_type": "attribute", "path": "."},
            {"param_name": "options", "node_type": "element", "path": "options", "required": False}
        ],
        example='''
        <function_calls>
        <invoke name="process_data">
        <parameter name="data">要处理的数据内容</parameter>
        <parameter name="format">json</parameter>
        <parameter name="options">{"validate": true}</parameter>
        </invoke>
        </function_calls>
        '''
    )
    async def process_data(
        self, 
        data: str, 
        format: str = "text",
        options: Optional[dict] = None
    ) -> ToolResult:
        """处理数据的主要方法
        
        Args:
            data: 输入数据
            format: 数据格式
            options: 处理选项
            
        Returns:
            ToolResult: 处理结果
        """
        try:
            # 参数验证
            if not data:
                return self.fail_response("数据参数不能为空")
            
            if format not in ["json", "text", "csv"]:
                return self.fail_response(f"不支持的格式: {format}")
            
            # 处理选项
            validate = True
            if options and isinstance(options, dict):
                validate = options.get('validate', True)
            
            logger.debug(f"处理数据 - 格式: {format}, 验证: {validate}")
            
            # 实际处理逻辑
            if format == "json" and validate:
                import json
                try:
                    parsed = json.loads(data)
                    result = {
                        "format": format,
                        "valid": True,
                        "processed": parsed
                    }
                except json.JSONDecodeError as e:
                    return self.fail_response(f"JSON 格式错误: {str(e)}")
            else:
                result = {
                    "format": format,
                    "length": len(data),
                    "processed": data[:100] + "..." if len(data) > 100 else data
                }
            
            logger.info(f"成功处理 {format} 格式的数据")
            return self.success_response(result)
            
        except Exception as e:
            logger.error(f"处理数据时出错: {str(e)}", exc_info=True)
            return self.fail_response(f"处理失败: {str(e)}")
```

### 2.2 带沙盒环境的工具

```python
from sandbox.tool_base import SandboxToolsBase
from agentpress.thread_manager import ThreadManager

class MySandboxTool(SandboxToolsBase):
    """需要沙盒环境的工具"""
    
    def __init__(self, project_id: str, thread_manager: ThreadManager):
        super().__init__(project_id, thread_manager)
        self.workspace_path = "/workspace"
    
    @openapi_schema({...})
    async def execute_in_sandbox(self, command: str) -> ToolResult:
        """在沙盒中执行操作"""
        try:
            # 确保沙盒已初始化
            await self._ensure_sandbox()
            
            # 使用沙盒文件系统
            files = self.sandbox.fs.list_files(self.workspace_path)
            
            # 执行命令
            result = await self.sandbox.shell.execute(command)
            
            return self.success_response({
                "output": result.output,
                "exit_code": result.exit_code
            })
            
        except Exception as e:
            return self.fail_response(str(e))
```

### 2.3 在 run.py 中注册工具

```python
# 默认注册（无 agent 配置时）
if enabled_tools is None:
    thread_manager.add_tool(MyCustomTool, config_param="production")

# 基于 agent 配置的条件注册
else:
    if enabled_tools.get('my_custom_tool', {}).get('enabled', False):
        tool_config = enabled_tools.get('my_custom_tool', {}).get('config', {})
        thread_manager.add_tool(
            MyCustomTool, 
            config_param=tool_config.get('param', 'default')
        )
```

## 3. 最佳实践

### 3.1 参数验证和错误处理

```python
async def process_file(self, file_path: str, mode: str = "r") -> ToolResult:
    """良好的参数验证示例"""
    
    # 1. 必需参数验证
    if not file_path:
        return self.fail_response("文件路径不能为空")
    
    # 2. 类型验证和转换
    if not isinstance(file_path, str):
        try:
            file_path = str(file_path)
        except:
            return self.fail_response("文件路径必须是字符串")
    
    # 3. 值域验证
    valid_modes = ["r", "w", "a", "rb", "wb"]
    if mode not in valid_modes:
        return self.fail_response(f"无效的模式: {mode}。支持的模式: {', '.join(valid_modes)}")
    
    # 4. 路径安全验证
    if ".." in file_path or file_path.startswith("/"):
        return self.fail_response("不允许使用绝对路径或父目录引用")
    
    try:
        # 实际操作
        result = await self._process_file_internal(file_path, mode)
        return self.success_response(result)
        
    except FileNotFoundError:
        return self.fail_response(f"文件不存在: {file_path}")
    except PermissionError:
        return self.fail_response(f"没有权限访问文件: {file_path}")
    except Exception as e:
        logger.error(f"处理文件时出错: {str(e)}", exc_info=True)
        return self.fail_response(f"处理失败: {str(e)}")
```

### 3.2 异步操作和资源管理

```python
class NetworkTool(Tool):
    """展示正确的资源管理"""
    
    def __init__(self):
        super().__init__()
        self.session = None
        self._lock = asyncio.Lock()
    
    async def _ensure_session(self):
        """确保 session 已初始化"""
        async with self._lock:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()
    
    async def fetch_data(self, url: str) -> ToolResult:
        """获取数据"""
        try:
            await self._ensure_session()
            
            async with self.session.get(url) as response:
                data = await response.text()
                return self.success_response({
                    "status": response.status,
                    "data": data
                })
                
        except Exception as e:
            return self.fail_response(str(e))
    
    async def cleanup(self):
        """清理资源"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
```

### 3.3 日志记录最佳实践

```python
async def complex_operation(self, params: dict) -> ToolResult:
    """展示分层日志记录"""
    
    operation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{operation_id}] 开始复杂操作，参数: {list(params.keys())}")
    
    try:
        # 调试级别 - 详细参数
        logger.debug(f"[{operation_id}] 完整参数: {params}")
        
        # 步骤 1
        logger.debug(f"[{operation_id}] 执行步骤 1...")
        result1 = await self._step1(params)
        
        # 步骤 2
        logger.debug(f"[{operation_id}] 执行步骤 2...")
        result2 = await self._step2(result1)
        
        # 成功
        logger.info(f"[{operation_id}] 操作成功完成")
        return self.success_response(result2)
        
    except Exception as e:
        logger.error(f"[{operation_id}] 操作失败: {str(e)}", exc_info=True)
        return self.fail_response(f"操作失败: {str(e)}")
```

### 3.4 描述文档最佳实践

```python
@openapi_schema({
    "type": "function",
    "function": {
        "name": "analyze_code",
        "description": """分析代码文件并提供详细报告。
        
        此工具可以：
        1. 检测代码质量问题
        2. 计算复杂度指标
        3. 识别潜在的 bug
        4. 提供改进建议
        
        支持的语言：Python, JavaScript, TypeScript, Java, Go
        
        使用场景：
        - 代码审查前的自动化检查
        - 识别需要重构的代码区域
        - 生成代码质量报告
        """,
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要分析的代码文件路径（相对于工作区）"
                },
                "checks": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["complexity", "bugs", "style", "security"]
                    },
                    "description": "要执行的检查类型。默认执行所有检查。"
                },
                "threshold": {
                    "type": "object",
                    "description": "各项指标的阈值设置",
                    "properties": {
                        "complexity": {
                            "type": "integer",
                            "description": "复杂度阈值（默认 10）",
                            "default": 10
                        }
                    }
                }
            },
            "required": ["file_path"]
        }
    }
})
```

## 4. 前端展示机制

### 4.1 通用工具视图

`GenericToolView.tsx` 处理大多数工具的标准展示：
- 自动解析工具输入/输出
- 显示执行状态（成功/失败/进行中）
- 格式化 JSON 输出

### 4.2 创建自定义工具视图

当需要特殊的展示逻辑时，创建自定义视图：

```typescript
// frontend/src/components/thread/tool-views/MyCustomToolView.tsx
import React from 'react';
import { ToolViewProps } from './types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

export function MyCustomToolView({
  name,
  assistantContent,
  toolContent,
  isSuccess,
  isStreaming
}: ToolViewProps) {
  // 解析工具特定的内容
  const parsedContent = React.useMemo(() => {
    if (!toolContent) return null;
    // 自定义解析逻辑
    return JSON.parse(toolContent);
  }, [toolContent]);
  
  return (
    <Card>
      <CardHeader>
        <h3>我的自定义工具</h3>
      </CardHeader>
      <CardContent>
        {/* 自定义展示逻辑 */}
      </CardContent>
    </Card>
  );
}
```

### 4.3 注册自定义视图

在工具视图路由中注册：

```typescript
// 在相应的工具视图管理器中添加
import { MyCustomToolView } from './MyCustomToolView';

const toolViews = {
  'my_custom_tool': MyCustomToolView,
  // ...其他工具视图
};
```

## 5. 高级功能

### 5.1 工具间协作

```python
class CollaborativeTool(Tool):
    """可以调用其他工具的工具示例"""
    
    def __init__(self, thread_manager: ThreadManager):
        super().__init__()
        self.thread_manager = thread_manager
    
    async def analyze_and_fix(self, file_path: str) -> ToolResult:
        """分析文件并自动修复问题"""
        
        # 1. 使用其他工具读取文件
        file_tool = self.thread_manager.tool_registry.get_tool("read_file")
        if file_tool:
            content = await file_tool['instance'].read_file(file_path)
            
        # 2. 分析内容
        issues = self._analyze(content)
        
        # 3. 如果有问题，使用编辑工具修复
        if issues:
            edit_tool = self.thread_manager.tool_registry.get_tool("edit_file")
            if edit_tool:
                await edit_tool['instance'].edit_file(file_path, fixes)
        
        return self.success_response({"fixed_issues": len(issues)})
```

### 5.2 动态工具加载（MCP）

MCP 工具包装器支持动态加载外部工具：

```python
# 配置 MCP 服务器
mcp_config = {
    'name': 'my-mcp-server',
    'qualifiedName': 'custom_sse_my_mcp_server',
    'config': {
        'url': 'http://localhost:3000/sse'
    },
    'enabledTools': ['tool1', 'tool2'],
    'instructions': '使用说明'
}

# MCPToolWrapper 会自动发现和注册工具
thread_manager.add_tool(MCPToolWrapper, mcp_configs=[mcp_config])
```

## 6. 测试和调试

### 6.1 单元测试模板

```python
import pytest
import asyncio
from my_custom_tool import MyCustomTool

class TestMyCustomTool:
    @pytest.fixture
    async def tool(self):
        """创建工具实例"""
        tool = MyCustomTool(config_param="test")
        yield tool
        # 清理资源
        if hasattr(tool, 'cleanup'):
            await tool.cleanup()
    
    @pytest.mark.asyncio
    async def test_process_data_success(self, tool):
        """测试成功场景"""
        result = await tool.process_data("test data", format="text")
        assert result.success
        assert "processed" in result.output
    
    @pytest.mark.asyncio
    async def test_process_data_validation(self, tool):
        """测试参数验证"""
        result = await tool.process_data("", format="text")
        assert not result.success
        assert "不能为空" in result.output
    
    @pytest.mark.asyncio
    async def test_process_data_error_handling(self, tool):
        """测试错误处理"""
        result = await tool.process_data("invalid json", format="json")
        assert not result.success
        assert "JSON 格式错误" in result.output
```

### 6.2 集成测试

```python
async def test_tool_in_thread_manager():
    """测试工具在 ThreadManager 中的集成"""
    thread_manager = ThreadManager()
    thread_manager.add_tool(MyCustomTool, config_param="integration")
    
    # 验证工具已注册
    schemas = thread_manager.tool_registry.get_openapi_schemas()
    tool_names = [s['function']['name'] for s in schemas]
    assert 'process_data' in tool_names
    
    # 测试工具调用
    tool = thread_manager.tool_registry.get_tool('process_data')
    assert tool is not None
```

### 6.3 调试技巧

1. **启用详细日志**
```python
import logging
logging.getLogger('my_custom_tool').setLevel(logging.DEBUG)
```

2. **添加断点调试**
```python
async def process_data(self, data: str) -> ToolResult:
    import pdb; pdb.set_trace()  # 调试断点
    # 或使用 VS Code 断点
```

3. **性能分析**
```python
import time

async def slow_operation(self) -> ToolResult:
    start_time = time.time()
    
    # 操作代码
    
    elapsed = time.time() - start_time
    logger.info(f"操作耗时: {elapsed:.2f}秒")
```

## 7. 常见问题和解决方案

### 7.1 工具未被识别
- 检查装饰器是否正确应用
- 确认工具已在 run.py 中注册
- 验证方法名称与 schema 中的 name 一致

### 7.2 参数解析错误
- 确保 XML mappings 正确配置
- 检查参数类型与 schema 定义匹配
- 注意可选参数的默认值处理

### 7.3 异步操作问题
- 使用 `async`/`await` 正确处理异步调用
- 避免在异步函数中使用阻塞操作
- 正确处理并发和资源竞争

## 总结

Suna 的工具系统提供了一个强大而灵活的框架，支持：
- 双模式（OpenAPI/XML）工具定义
- 完善的参数验证和错误处理
- 沙盒环境集成
- 动态工具加载
- 自定义前端展示

遵循本文档的最佳实践，可以快速开发出稳定、易用的自定义工具，扩展 Suna 的功能。