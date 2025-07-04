# Suna 工具执行失败处理机制

## 概述

Suna 采用多层次的错误处理架构来确保工具执行失败时的稳定性和可追踪性。本文档详细介绍了从工具层到响应层的完整错误处理流程。

## 错误处理架构

### 1. 工具层错误处理

每个工具在 `execute()` 方法中使用 try-catch 块捕获异常：

```python
# src/suna/tool/base_tool.py:48-52
try:
    # 执行具体逻辑
    result = self._do_work()
    return self.success_response(result)
except Exception as e:
    return self.fail_response(f"执行失败: {str(e)}")
```

**标准化错误响应**：
- `fail_response()` 方法返回统一格式的错误结果
- 包含 `success=False` 标志和错误消息
- 保持工具接口的一致性

### 2. 执行层错误处理

`ToolExecutor._execute_tool()` 方法捕获未处理的异常：

```python
# src/suna/jobs/thread_run_executor.py:245-252
try:
    result = await tool.execute(tool_call)
except Exception as e:
    logger.error(f"Tool execution failed: {e}", exc_info=True)
    return ToolResult(
        success=False,
        content=f"Tool execution failed: {str(e)}",
        tool_name=tool_call.name
    )
```

**关键特性**：
- 捕获所有未处理的异常
- 记录详细的错误日志和堆栈跟踪
- 返回标准化的 `ToolResult` 对象

### 3. 策略层错误处理

#### 顺序执行策略
```python
# src/suna/jobs/thread_run_executor.py:顺序执行
for idx, tool_call in enumerate(tool_calls):
    result = await self._execute_tool(tool_call, idx)
    results.append(result)
    
    # 特殊工具终止后续执行
    if tool_call.name in ["ask", "complete"]:
        break
```

**特点**：
- 单个工具失败不阻止后续工具执行
- `ask` 和 `complete` 工具会终止执行链
- 返回所有工具的执行结果（包括失败的）

#### 并行执行策略
```python
# src/suna/jobs/thread_run_executor.py:并行执行
tasks = [
    self._execute_tool(tool_call, idx) 
    for idx, tool_call in enumerate(tool_calls)
]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

**特点**：
- 使用 `return_exceptions=True` 隔离失败
- 所有工具独立执行，互不影响
- 异常被转换为结果而非传播

### 4. 状态报告机制

错误通过状态消息实时报告：

```python
# 工具开始执行
await self.report_status("tool_started", {
    "tool_name": tool_call.name,
    "tool_index": tool_index,
    "thread_run_id": self.thread_run_id
})

# 工具执行失败
if not result.success:
    await self.report_status("tool_failed", {
        "tool_name": tool_call.name,
        "tool_index": tool_index,
        "error": result.content,
        "thread_run_id": self.thread_run_id
    })

# 工具执行异常
await self.report_status("tool_error", {
    "tool_name": tool_call.name,
    "tool_index": tool_index,
    "error": str(e),
    "thread_run_id": self.thread_run_id
})
```

### 5. 响应处理层

`ResponseProcessor` 捕获所有错误：

```python
# src/suna/response_processor.py
try:
    # 处理响应
except Exception as e:
    logger.error(f"Error processing response: {e}")
    await self.report_error(str(e))
```

### 6. 持久化层

`ThreadManager` 确保错误状态保存到数据库：

```python
# src/suna/storage/thread_manager.py
def add_status_message(self, status_type: str, message: dict):
    """添加状态消息到数据库"""
    status_message = StatusMessage(
        thread_id=self.thread_id,
        run_id=self.run_id,
        status_type=status_type,
        message=message,
        timestamp=datetime.utcnow()
    )
    self.session.add(status_message)
    self.session.commit()
```

## 错误恢复机制

### 1. 部分结果恢复
- 顺序执行时，即使某个工具失败，后续工具仍会执行
- 并行执行时，一个工具失败不影响其他工具
- 最终结果包含所有工具的执行状态

### 2. 资源清理
工具可以在错误处理器中实现资源清理：

```python
class CustomTool(BaseTool):
    def execute(self, tool_call):
        resource = None
        try:
            resource = self.acquire_resource()
            return self.process(resource)
        except Exception as e:
            return self.fail_response(str(e))
        finally:
            if resource:
                self.release_resource(resource)
```

### 3. 终止执行
特定工具（`ask`、`complete`）失败时会终止后续执行：
- 用于需要用户确认的场景
- 防止在关键步骤失败后继续执行

## 错误监控和调试

### 1. 日志记录
```python
logger.error(f"Tool execution failed: {e}", exc_info=True)
```
- 记录完整的堆栈跟踪
- 包含工具名称、参数等上下文

### 2. 分布式追踪
集成 Langfuse 进行错误追踪：
```python
# 错误自动上报到 Langfuse
trace.update(
    output={"error": str(e)},
    metadata={"status": "failed"}
)
```

### 3. 元数据支持
错误消息包含丰富的元数据：
- `thread_run_id`：执行链路标识
- `tool_index`：工具执行顺序
- `timestamp`：错误发生时间
- `tool_name`：失败的工具名称

## 最佳实践

### 1. 工具开发者
- 在 `execute()` 方法中使用 try-catch 包装所有逻辑
- 使用 `fail_response()` 返回友好的错误消息
- 在 finally 块中清理资源
- 避免让异常逃逸到执行层

### 2. 错误消息
- 提供清晰、可操作的错误描述
- 包含足够的上下文信息
- 避免暴露敏感信息
- 使用结构化的错误格式

### 3. 重试策略
虽然 Suna 提供了重试工具（`utils/retry.py`），但未直接集成到工具执行中。需要重试的工具应：
- 在工具内部实现重试逻辑
- 使用指数退避策略
- 设置合理的重试次数上限

## 示例：自定义工具错误处理

```python
class DatabaseQueryTool(BaseTool):
    def execute(self, tool_call: ToolCall) -> ToolResult:
        conn = None
        try:
            # 参数验证
            query = tool_call.arguments.get("query")
            if not query:
                return self.fail_response("查询语句不能为空")
            
            # 获取连接
            conn = self.get_connection()
            
            # 执行查询
            result = conn.execute(query)
            
            # 返回成功结果
            return self.success_response({
                "rows": result.fetchall(),
                "row_count": result.rowcount
            })
            
        except ConnectionError as e:
            # 连接错误
            return self.fail_response(f"数据库连接失败: {str(e)}")
            
        except QueryError as e:
            # 查询错误
            return self.fail_response(f"查询执行失败: {str(e)}")
            
        except Exception as e:
            # 未知错误
            logger.error(f"Unexpected error in DatabaseQueryTool: {e}", exc_info=True)
            return self.fail_response("查询过程中发生未知错误")
            
        finally:
            # 清理资源
            if conn:
                conn.close()
```

## 总结

Suna 的工具错误处理机制通过多层防护确保系统稳定性：

1. **工具层**提供标准化的错误响应
2. **执行层**捕获未处理的异常
3. **策略层**处理部分失败情况
4. **状态报告**实时传递错误信息
5. **持久化层**确保错误可追溯

这种设计使得系统能够优雅地处理各种失败场景，同时为开发者提供充分的调试信息。