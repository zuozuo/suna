# Suna 自定义工具开发指南

## 概述

本指南详细介绍如何在 Suna 平台中创建自定义工具。Suna 的工具系统设计灵活且强大，支持 OpenAI Function Calling 和 Anthropic XML 双模态格式，让您能够轻松扩展平台功能。

## 目录

1. [工具系统架构](#工具系统架构)
2. [创建第一个自定义工具](#创建第一个自定义工具)
3. [高级工具开发](#高级工具开发)
4. [前端集成](#前端集成)
5. [测试和调试](#测试和调试)
6. [最佳实践](#最佳实践)
7. [常见问题](#常见问题)

## 工具系统架构

### 核心组件

```
backend/agent/tools/
├── __init__.py          # 工具导出
├── base.py              # Tool 基类
├── registry.py          # 工具注册表
├── decorators.py        # 工具装饰器
└── implementations/     # 具体工具实现
    ├── browser_tools.py
    ├── file_tools.py
    ├── shell_tools.py
    └── ...
```

### 工具生命周期

```mermaid
graph LR
    A[定义工具类] --> B[注册到 ToolRegistry]
    B --> C[LLM 调用工具]
    C --> D[ThreadManager 执行]
    D --> E[返回结果]
    E --> F[前端展示]
```

## 创建第一个自定义工具

### 1. 基础工具模板

创建文件 `backend/agent/tools/implementations/weather_tool.py`：

```python
from typing import Optional, Dict, Any
from agent.tools.base import Tool, tool
import aiohttp

@tool
class WeatherTool(Tool):
    """获取指定城市的天气信息"""
    
    name = "get_weather"
    description = "Get current weather information for a specified city"
    
    # 参数定义（JSON Schema）
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name (e.g., 'Shanghai', 'New York')"
            },
            "units": {
                "type": "string",
                "description": "Temperature units",
                "enum": ["celsius", "fahrenheit"],
                "default": "celsius"
            }
        },
        "required": ["city"]
    }
    
    async def execute(self, city: str, units: str = "celsius") -> Dict[str, Any]:
        """执行工具逻辑"""
        try:
            # 调用天气 API（示例）
            async with aiohttp.ClientSession() as session:
                url = f"https://api.weather.com/v1/current"
                params = {"city": city, "units": units}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "data": {
                                "city": city,
                                "temperature": data["temp"],
                                "description": data["description"],
                                "humidity": data["humidity"],
                                "units": units
                            }
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Weather API returned status {response.status}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get weather: {str(e)}"
            }
```

### 2. 注册工具

在 `backend/agent/tools/__init__.py` 中添加：

```python
from .implementations.weather_tool import WeatherTool

# 添加到导出列表
__all__ = [
    # ... 其他工具
    "WeatherTool",
]

# 注册到默认工具列表
DEFAULT_TOOLS = [
    # ... 其他工具
    WeatherTool,
]
```

### 3. 配置工具加载

在 `backend/agent/tools/registry.py` 中，工具会自动被注册：

```python
class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._load_default_tools()
    
    def _load_default_tools(self):
        """加载默认工具"""
        from agent.tools import DEFAULT_TOOLS
        
        for tool_class in DEFAULT_TOOLS:
            tool_instance = tool_class()
            self.register(tool_instance)
    
    def register(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
```

## 高级工具开发

### 1. 带沙盒环境的工具

对于需要执行代码或系统命令的工具，使用沙盒环境：

```python
from agent.tools.base import Tool, tool
from agent.sandbox import SandboxManager

@tool
class CodeExecutionTool(Tool):
    """在沙盒环境中执行 Python 代码"""
    
    name = "execute_python"
    description = "Execute Python code in a secure sandbox environment"
    
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Execution timeout in seconds",
                "default": 30
            }
        },
        "required": ["code"]
    }
    
    def __init__(self):
        super().__init__()
        self.sandbox_manager = SandboxManager()
    
    async def execute(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """在沙盒中执行代码"""
        try:
            # 获取或创建沙盒会话
            session = await self.sandbox_manager.get_or_create_session(
                session_id=self.context.get("session_id")
            )
            
            # 执行代码
            result = await session.execute_code(
                code=code,
                language="python",
                timeout=timeout
            )
            
            return {
                "success": True,
                "output": result.stdout,
                "error": result.stderr if result.stderr else None,
                "execution_time": result.execution_time
            }
            
        except TimeoutError:
            return {
                "success": False,
                "error": f"Code execution timed out after {timeout} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Execution failed: {str(e)}"
            }
```

### 2. 带状态的工具

某些工具需要维护会话状态：

```python
from agent.tools.base import Tool, tool
from typing import Dict, Any, Optional
import uuid

@tool
class DatabaseQueryTool(Tool):
    """执行数据库查询的工具"""
    
    name = "database_query"
    description = "Execute SQL queries on a connected database"
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["connect", "query", "disconnect"],
                "description": "Action to perform"
            },
            "connection_string": {
                "type": "string",
                "description": "Database connection string (for connect action)"
            },
            "query": {
                "type": "string", 
                "description": "SQL query to execute (for query action)"
            }
        },
        "required": ["action"]
    }
    
    def __init__(self):
        super().__init__()
        self.connections: Dict[str, Any] = {}
    
    async def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """执行数据库操作"""
        session_id = self.context.get("session_id", "default")
        
        if action == "connect":
            return await self._connect(session_id, kwargs.get("connection_string"))
        elif action == "query":
            return await self._query(session_id, kwargs.get("query"))
        elif action == "disconnect":
            return await self._disconnect(session_id)
        
    async def _connect(self, session_id: str, connection_string: str) -> Dict[str, Any]:
        """建立数据库连接"""
        try:
            # 实际的数据库连接逻辑
            conn = await create_connection(connection_string)
            self.connections[session_id] = conn
            
            return {
                "success": True,
                "message": "Connected to database successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection failed: {str(e)}"
            }
```

### 3. 复合工具（调用其他工具）

```python
@tool  
class DataAnalysisTool(Tool):
    """数据分析工具，结合文件读取和代码执行"""
    
    name = "analyze_data"
    description = "Analyze data from CSV files using pandas"
    
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the CSV file"
            },
            "analysis_type": {
                "type": "string",
                "enum": ["summary", "correlation", "visualization"],
                "description": "Type of analysis to perform"
            }
        },
        "required": ["file_path", "analysis_type"]
    }
    
    async def execute(self, file_path: str, analysis_type: str) -> Dict[str, Any]:
        """执行数据分析"""
        # 获取工具注册表
        registry = self.context.get("tool_registry")
        
        # 1. 使用文件读取工具
        read_file_tool = registry.get_tool("read_file")
        file_content = await read_file_tool.execute(file_path=file_path)
        
        if not file_content["success"]:
            return file_content
        
        # 2. 生成分析代码
        analysis_code = self._generate_analysis_code(
            file_path=file_path,
            analysis_type=analysis_type
        )
        
        # 3. 使用代码执行工具
        execute_code_tool = registry.get_tool("execute_python")
        result = await execute_code_tool.execute(code=analysis_code)
        
        return result
    
    def _generate_analysis_code(self, file_path: str, analysis_type: str) -> str:
        """生成分析代码"""
        if analysis_type == "summary":
            return f"""
import pandas as pd
df = pd.read_csv("{file_path}")
print(df.describe())
print("\\nShape:", df.shape)
print("\\nColumns:", df.columns.tolist())
"""
        # ... 其他分析类型
```

## 前端集成

### 1. 通用工具视图

大多数工具可以使用通用视图 `GenericToolView`：

```typescript
// frontend/src/components/tools/GenericToolView.tsx
export function GenericToolView({ tool, result }) {
  if (!result) return null;
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>{tool.name}</CardTitle>
      </CardHeader>
      <CardContent>
        {result.success ? (
          <pre className="bg-gray-100 p-4 rounded">
            {JSON.stringify(result.data, null, 2)}
          </pre>
        ) : (
          <Alert variant="destructive">
            <AlertDescription>{result.error}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
```

### 2. 自定义工具视图

为天气工具创建专门的视图：

```typescript
// frontend/src/components/tools/WeatherToolView.tsx
import { Card, CardContent } from "@/components/ui/card";
import { Cloud, Droplets, Thermometer } from "lucide-react";

interface WeatherData {
  city: string;
  temperature: number;
  description: string;
  humidity: number;
  units: string;
}

export function WeatherToolView({ result }) {
  if (!result?.success || !result.data) {
    return <GenericToolView result={result} />;
  }
  
  const weather: WeatherData = result.data;
  const tempUnit = weather.units === "celsius" ? "°C" : "°F";
  
  return (
    <Card className="w-full max-w-md">
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-2xl font-bold">{weather.city}</h3>
          <Cloud className="w-8 h-8 text-blue-500" />
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center space-x-2">
            <Thermometer className="w-5 h-5 text-orange-500" />
            <div>
              <p className="text-sm text-gray-500">Temperature</p>
              <p className="text-xl font-semibold">
                {weather.temperature}{tempUnit}
              </p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <Droplets className="w-5 h-5 text-blue-500" />
            <div>
              <p className="text-sm text-gray-500">Humidity</p>
              <p className="text-xl font-semibold">{weather.humidity}%</p>
            </div>
          </div>
        </div>
        
        <p className="mt-4 text-center text-gray-600">
          {weather.description}
        </p>
      </CardContent>
    </Card>
  );
}
```

### 3. 注册工具视图

在 `frontend/src/components/tools/ToolViewRegistry.tsx` 中注册：

```typescript
import { WeatherToolView } from "./WeatherToolView";

export const toolViewRegistry = {
  // ... 其他工具视图
  "get_weather": WeatherToolView,
};
```

## 测试和调试

### 1. 单元测试

创建 `backend/tests/test_weather_tool.py`：

```python
import pytest
from unittest.mock import AsyncMock, patch
from agent.tools.implementations.weather_tool import WeatherTool

@pytest.mark.asyncio
async def test_weather_tool_success():
    """测试成功获取天气"""
    tool = WeatherTool()
    
    # Mock API 响应
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "temp": 25,
        "description": "Sunny",
        "humidity": 60
    })
    
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        result = await tool.execute(city="Shanghai", units="celsius")
    
    assert result["success"] is True
    assert result["data"]["temperature"] == 25
    assert result["data"]["city"] == "Shanghai"

@pytest.mark.asyncio
async def test_weather_tool_api_error():
    """测试 API 错误处理"""
    tool = WeatherTool()
    
    mock_response = AsyncMock()
    mock_response.status = 500
    
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        result = await tool.execute(city="Shanghai")
    
    assert result["success"] is False
    assert "status 500" in result["error"]
```

### 2. 集成测试

```python
@pytest.mark.integration
async def test_weather_tool_in_thread():
    """测试工具在对话线程中的执行"""
    thread_manager = ThreadManager()
    
    # 创建测试线程
    thread = await thread_manager.create_thread(
        user_id="test_user",
        name="Weather Test"
    )
    
    # 发送包含工具调用的消息
    message = {
        "role": "user",
        "content": "What's the weather in Shanghai?",
        "tool_calls": [{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"city": "Shanghai"}'
            }
        }]
    }
    
    result = await thread_manager.add_message(
        thread_id=thread.id,
        message=message
    )
    
    assert result is not None
    assert len(result.tool_results) == 1
```

### 3. 调试技巧

```python
@tool
class DebugEnabledTool(Tool):
    """带调试功能的工具基类"""
    
    def __init__(self):
        super().__init__()
        self.debug = os.getenv("TOOL_DEBUG", "false").lower() == "true"
    
    async def execute(self, **kwargs):
        """执行工具并记录调试信息"""
        if self.debug:
            logger.debug(f"Executing {self.name} with args: {kwargs}")
            logger.debug(f"Context: {self.context}")
        
        try:
            result = await self._execute_internal(**kwargs)
            
            if self.debug:
                logger.debug(f"Result: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Tool {self.name} failed: {str(e)}", exc_info=True)
            
            if self.debug:
                import traceback
                return {
                    "success": False,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            
            return {
                "success": False,
                "error": str(e)
            }
```

## 最佳实践

### 1. 参数验证

```python
from pydantic import BaseModel, Field, validator

class WeatherParams(BaseModel):
    """天气工具参数模型"""
    city: str = Field(..., description="City name")
    units: str = Field("celsius", description="Temperature units")
    
    @validator("units")
    def validate_units(cls, v):
        if v not in ["celsius", "fahrenheit"]:
            raise ValueError("Units must be 'celsius' or 'fahrenheit'")
        return v

@tool
class ValidatedWeatherTool(Tool):
    """使用 Pydantic 验证的天气工具"""
    
    async def execute(self, **kwargs):
        # 验证参数
        try:
            params = WeatherParams(**kwargs)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid parameters: {str(e)}"
            }
        
        # 使用验证后的参数
        return await self._get_weather(params.city, params.units)
```

### 2. 错误处理

```python
class ToolError(Exception):
    """工具执行错误基类"""
    pass

class ToolTimeoutError(ToolError):
    """工具超时错误"""
    pass

class ToolValidationError(ToolError):
    """参数验证错误"""
    pass

@tool
class RobustTool(Tool):
    """健壮的工具实现"""
    
    async def execute(self, **kwargs):
        try:
            # 参数验证
            self._validate_params(kwargs)
            
            # 设置超时
            return await asyncio.wait_for(
                self._execute_internal(**kwargs),
                timeout=30.0
            )
            
        except ToolValidationError as e:
            return {"success": False, "error": str(e), "type": "validation"}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Tool execution timed out", "type": "timeout"}
        except Exception as e:
            logger.exception(f"Unexpected error in {self.name}")
            return {"success": False, "error": str(e), "type": "unknown"}
```

### 3. 资源管理

```python
@tool
class ResourceManagedTool(Tool):
    """正确管理资源的工具"""
    
    async def execute(self, **kwargs):
        resources = []
        try:
            # 获取资源
            db_conn = await self._get_db_connection()
            resources.append(db_conn)
            
            file_handle = await self._open_file(kwargs["file_path"])
            resources.append(file_handle)
            
            # 执行操作
            result = await self._process_data(db_conn, file_handle)
            
            return {"success": True, "data": result}
            
        finally:
            # 确保资源被释放
            for resource in reversed(resources):
                try:
                    await resource.close()
                except Exception as e:
                    logger.warning(f"Failed to close resource: {e}")
```

### 4. 日志记录

```python
import structlog

logger = structlog.get_logger()

@tool
class LoggedTool(Tool):
    """带结构化日志的工具"""
    
    async def execute(self, **kwargs):
        # 记录开始
        logger.info("tool_execution_started",
            tool_name=self.name,
            params=kwargs,
            session_id=self.context.get("session_id"),
            user_id=self.context.get("user_id")
        )
        
        start_time = time.time()
        
        try:
            result = await self._execute_internal(**kwargs)
            
            # 记录成功
            logger.info("tool_execution_completed",
                tool_name=self.name,
                duration=time.time() - start_time,
                success=result.get("success", False)
            )
            
            return result
            
        except Exception as e:
            # 记录失败
            logger.error("tool_execution_failed",
                tool_name=self.name,
                duration=time.time() - start_time,
                error=str(e),
                exc_info=True
            )
            raise
```

## 常见问题

### Q1: 工具没有被 LLM 调用

**可能原因：**
1. 工具描述不够清晰
2. 参数定义不正确
3. 工具未正确注册

**解决方案：**
```python
@tool
class WellDescribedTool(Tool):
    name = "calculate_mortgage"
    description = """Calculate monthly mortgage payment.
    
    Use this tool when the user asks about:
    - Mortgage payments
    - Home loan calculations
    - Monthly payment amounts for property
    
    This tool calculates the monthly payment for a fixed-rate mortgage.
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "principal": {
                "type": "number",
                "description": "Loan amount in dollars"
            },
            "annual_rate": {
                "type": "number",
                "description": "Annual interest rate as percentage (e.g., 4.5 for 4.5%)"
            },
            "years": {
                "type": "integer",
                "description": "Loan term in years"
            }
        },
        "required": ["principal", "annual_rate", "years"]
    }
```

### Q2: 工具执行超时

**解决方案：**
```python
@tool
class TimeoutAwareTool(Tool):
    
    async def execute(self, **kwargs):
        timeout = kwargs.pop("timeout", 30)  # 允许自定义超时
        
        try:
            return await asyncio.wait_for(
                self._long_running_task(**kwargs),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            # 尝试清理
            await self._cleanup()
            return {
                "success": False,
                "error": f"Operation timed out after {timeout} seconds"
            }
```

### Q3: 工具结果太大

**解决方案：**
```python
@tool
class LargeResultTool(Tool):
    
    async def execute(self, **kwargs):
        result = await self._generate_large_result(**kwargs)
        
        # 检查结果大小
        result_size = len(json.dumps(result))
        
        if result_size > 100_000:  # 100KB 限制
            # 保存到文件
            file_id = str(uuid.uuid4())
            file_path = f"/tmp/tool_results/{file_id}.json"
            
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(json.dumps(result))
            
            return {
                "success": True,
                "data": {
                    "type": "large_result",
                    "file_id": file_id,
                    "size": result_size,
                    "preview": result[:1000]  # 前1000字符预览
                }
            }
        
        return {"success": True, "data": result}
```

### Q4: 工具需要用户授权

**解决方案：**
```python
@tool
class AuthorizedTool(Tool):
    
    async def execute(self, **kwargs):
        # 检查授权
        user_id = self.context.get("user_id")
        
        if not await self._check_authorization(user_id):
            return {
                "success": False,
                "error": "Authorization required",
                "auth_url": f"/auth/tool/{self.name}?user={user_id}"
            }
        
        # 执行授权后的操作
        return await self._execute_authorized(**kwargs)
```

## 总结

创建自定义工具的关键步骤：

1. **定义工具类**：继承 `Tool` 基类，使用 `@tool` 装饰器
2. **设置元数据**：name、description、parameters
3. **实现 execute 方法**：处理工具逻辑
4. **注册工具**：添加到工具列表
5. **创建前端视图**（可选）：提供更好的用户体验
6. **编写测试**：确保工具可靠性
7. **文档化**：让其他开发者理解如何使用

遵循本指南的最佳实践，您可以创建出强大、可靠且易于维护的自定义工具，为 Suna 平台增加新的功能。