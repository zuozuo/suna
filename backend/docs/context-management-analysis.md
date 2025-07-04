# Suna 上下文管理系统深度分析

## 1. 概述

Suna 的上下文管理系统是一个多层次、分布式的架构，主要包含以下几个层面：

1. **对话上下文管理**：管理 LLM 对话的 token 计数和自动摘要
2. **异步执行上下文**：基于 Python 的 `asyncio` 和 `contextvars` 实现请求级别的隔离
3. **分布式上下文同步**：通过 Redis 实现跨进程的状态同步
4. **工具执行上下文**：管理工具调用的状态和结果

## 2. 对话上下文管理（ContextManager）

### 2.1 核心实现

`ContextManager` 类（`backend/agentpress/context_manager.py`）负责管理 LLM 对话的上下文窗口：

```python
class ContextManager:
    def __init__(self, token_threshold: int = DEFAULT_TOKEN_THRESHOLD):
        self.db = DBConnection()
        self.token_threshold = token_threshold  # 默认 120,000 tokens
```

### 2.2 Token 计数机制

使用 `litellm` 库进行准确的模型特定 token 计算：

```python
async def get_thread_token_count(self, thread_id: str) -> int:
    messages = await self.get_messages_for_summarization(thread_id)
    
    # 使用 litellm 的 token_counter 进行准确计数
    token_count = token_counter(model="gpt-4", messages=messages)
    
    logger.info(f"Thread {thread_id} has {token_count} tokens")
    return token_count
```

### 2.3 自动摘要策略

当对话超过阈值时，自动生成摘要以压缩上下文：

```python
async def check_and_summarize_if_needed(
    self, 
    thread_id: str, 
    add_message_callback, 
    model: str = "gpt-4o-mini",
    force: bool = False
) -> bool:
    token_count = await self.get_thread_token_count(thread_id)
    
    if token_count < self.token_threshold and not force:
        return False
    
    messages = await self.get_messages_for_summarization(thread_id)
    
    if len(messages) < 3:
        return False
    
    summary = await self.create_summary(thread_id, messages, model)
    
    if summary:
        await add_message_callback(
            thread_id=thread_id,
            type="summary",
            content=summary,
            is_llm_message=True,
            metadata={"token_count": token_count}
        )
        return True
```

### 2.4 摘要内容格式

摘要使用特定格式，确保关键信息不丢失：

```python
formatted_summary = f"""
======== CONVERSATION HISTORY SUMMARY ========

{summary_content}

======== END OF SUMMARY ========

The above is a summary of the conversation history. The conversation continues below.
"""
```

## 3. 异步执行上下文管理

### 3.1 Context Variables 使用

通过 `contextvars` 实现请求级别的上下文隔离（`backend/utils/logger.py`）：

```python
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,  # 合并上下文变量
        # ... 其他处理器
    ]
)
```

### 3.2 请求上下文注入

在 FastAPI 中间件中为每个请求创建唯一上下文（`backend/api.py:91-121`）：

```python
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    # 清理之前的上下文变量
    structlog.contextvars.clear_contextvars()
    
    request_id = str(uuid.uuid4())
    
    # 绑定请求相关的上下文变量
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        client_ip=request.client.host,
        method=request.method,
        path=request.url.path,
        query_params=str(request.query_params)
    )
    
    logger.info(f"Request started: {method} {path}")
    
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Request failed: {method} {path} | Error: {str(e)}")
        raise
```

### 3.3 Agent Run 上下文传递

在 agent 运行时绑定额外的上下文信息（`backend/agent/api.py:374-376`）：

```python
structlog.contextvars.bind_contextvars(
    thread_id=thread_id,
    agent_run_id=agent_run_id,
)
```

## 4. FastAPI 生命周期管理

### 4.1 应用启动和关闭

使用 `asynccontextmanager` 管理全局资源（`backend/api.py:43-88`）：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting up FastAPI application with instance ID: {instance_id}")
    
    try:
        # 启动时初始化资源
        await db.initialize()
        
        # 初始化各个模块
        agent_api.initialize(db, instance_id)
        sandbox_api.initialize(db)
        
        # 初始化 Redis 连接
        await redis.initialize_async()
        
        yield  # 应用运行期间
        
        # 关闭时清理资源
        logger.info("Cleaning up agent resources")
        await agent_api.cleanup()
        
        await redis.close()
        await db.disconnect()
        
    except Exception as e:
        logger.error(f"Error during application startup: {e}")
        raise
```

### 4.2 数据库连接管理

数据库连接使用单例模式和异步客户端：

```python
class DBConnection:
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self):
        if not self._client:
            self._client = create_async_client(
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_ANON_KEY
            )
```

## 5. 工具执行上下文

### 5.1 ToolExecutionContext 数据类

定义工具执行的完整上下文（`backend/agentpress/response_processor.py:36-47`）：

```python
@dataclass
class ToolExecutionContext:
    """Context for a tool execution including call details, result, and display info."""
    tool_call: Dict[str, Any]
    tool_index: int
    result: Optional[ToolResult] = None
    function_name: Optional[str] = None
    xml_tag_name: Optional[str] = None
    error: Optional[Exception] = None
    assistant_message_id: Optional[str] = None
    parsing_details: Optional[Dict[str, Any]] = None
```

### 5.2 工具执行策略

支持顺序和并行执行策略：

```python
@dataclass
class ProcessorConfig:
    tool_execution_strategy: ToolExecutionStrategy = "sequential"  # 或 "parallel"
    execute_tools: bool = True
    execute_on_stream: bool = False
    # ... 其他配置
```

### 5.3 响应处理器上下文传递

在 `ResponseProcessor` 中保持执行上下文（`backend/agentpress/response_processor.py:86-107`）：

```python
class ResponseProcessor:
    def __init__(self, tool_registry, add_message_callback, trace=None, 
                 is_agent_builder=False, target_agent_id=None, agent_config=None):
        self.tool_registry = tool_registry
        self.add_message = add_message_callback
        self.trace = trace or langfuse.trace(name="anonymous:response_processor")
        self.is_agent_builder = is_agent_builder
        self.target_agent_id = target_agent_id
        self.agent_config = agent_config
```

## 6. Redis 在上下文管理中的作用

### 6.1 分布式锁机制

防止并发执行同一个 agent run（`backend/run_agent_background.py`）：

```python
# 注册运行实例
instance_key = f"active_run:{instance_id}:{agent_run_id}"
await redis.set(instance_key, "running", ex=redis.REDIS_KEY_TTL)

# 定期刷新 TTL
if total_responses % 50 == 0:
    await redis.expire(instance_active_key, redis.REDIS_KEY_TTL)
```

### 6.2 发布订阅机制

用于跨进程的控制信号传递：

```python
# 订阅控制通道
pubsub = await redis.create_pubsub()
await pubsub.subscribe(instance_control_channel, global_control_channel)

# 检查停止信号
async def check_for_stop_signal():
    async for message in pubsub.listen():
        if message['type'] == 'message':
            data = message['data']
            if data == 'STOP':
                stop_signal_received = True
                break
```

### 6.3 响应缓存

使用 Redis list 存储 agent 响应：

```python
# 存储响应
response_json = json.dumps(response)
await redis.rpush(response_list_key, response_json)
await redis.publish(response_channel, "new")

# 获取所有响应
all_responses_json = await redis.lrange(response_list_key, 0, -1)
```

## 7. ThreadManager 中的上下文集成

### 7.1 初始化时的上下文设置

`ThreadManager` 集成了多个上下文管理组件（`backend/agentpress/thread_manager.py:41-66`）：

```python
def __init__(self, trace=None, is_agent_builder=False, 
             target_agent_id=None, agent_config=None):
    self.db = DBConnection()
    self.tool_registry = ToolRegistry()
    self.trace = trace or langfuse.trace(name="anonymous:thread_manager")
    self.is_agent_builder = is_agent_builder
    self.target_agent_id = target_agent_id
    self.agent_config = agent_config
    
    # 初始化响应处理器，传递所有上下文
    self.response_processor = ResponseProcessor(
        tool_registry=self.tool_registry,
        add_message_callback=self.add_message,
        trace=self.trace,
        is_agent_builder=self.is_agent_builder,
        target_agent_id=self.target_agent_id,
        agent_config=self.agent_config
    )
    
    # 初始化上下文管理器
    self.context_manager = ContextManager()
```

### 7.2 消息压缩策略

为了优化上下文使用，对长消息进行压缩：

```python
def _compress_message(self, msg_content, message_id=None, max_length=3000):
    if isinstance(msg_content, str):
        if len(msg_content) > max_length:
            return msg_content[:max_length] + "... (truncated)" + \
                   f"\n\nmessage_id \"{message_id}\"\n" + \
                   "Use expand-message tool to see contents"
    # ... 处理其他类型
```

## 8. 并发和异步上下文管理

### 8.1 任务创建和上下文继承

创建异步任务时，自动继承父任务的上下文：

```python
# 创建后台任务，上下文自动传递
stop_checker = asyncio.create_task(check_for_stop_signal())

# 在新任务中，contextvars 自动可用
request_id = structlog.contextvars.get_contextvars().get('request_id')
```

### 8.2 流式响应中的上下文保持

在异步生成器中保持上下文：

```python
async def stream_generator():
    # 创建独立的 Redis 订阅以保持上下文
    pubsub = await redis.create_pubsub()
    try:
        async for message in pubsub.listen():
            # 上下文在整个流式过程中保持
            yield f"data: {message['data']}\n\n"
    finally:
        await pubsub.close()
```

## 9. 上下文管理最佳实践

### 9.1 资源清理

始终使用 try-finally 或上下文管理器确保资源清理：

```python
pubsub = await redis.create_pubsub()
try:
    # 使用资源
    await pubsub.subscribe(channel)
finally:
    # 确保清理
    await pubsub.close()
```

### 9.2 上下文隔离

每个请求/任务有独立的上下文，避免数据泄露：

```python
# 请求开始时清理旧上下文
structlog.contextvars.clear_contextvars()

# 绑定新的上下文
structlog.contextvars.bind_contextvars(
    request_id=str(uuid.uuid4())
)
```

### 9.3 错误处理中的上下文保持

错误处理时保留上下文信息用于调试：

```python
try:
    response = await call_next(request)
except Exception as e:
    # 上下文信息自动包含在日志中
    logger.error(f"Request failed: {method} {path} | Error: {str(e)}")
    raise
```

## 10. 性能优化

### 10.1 连接池复用

通过单例模式和连接池减少上下文切换开销：

```python
# 数据库连接池
self._client = create_async_client(...)

# Redis 连接池
self._redis_client = await aioredis.from_url(...)
```

### 10.2 批量操作

减少上下文切换次数：

```python
# 批量 Redis 操作
pending_redis_operations = []
pending_redis_operations.append(asyncio.create_task(redis.rpush(...)))
pending_redis_operations.append(asyncio.create_task(redis.publish(...)))

# 等待所有操作完成
await asyncio.gather(*pending_redis_operations)
```

### 10.3 上下文压缩

通过摘要和消息压缩减少内存使用：

```python
# 自动摘要减少 token 数量
if token_count > self.token_threshold:
    await self.create_summary(...)

# 消息压缩减少传输量
compressed = self._compress_message(content, max_length=3000)
```

## 11. 监控和调试

### 11.1 分布式追踪

通过 Langfuse 实现完整的调用链追踪：

```python
trace = langfuse.trace(
    name="agent_run", 
    id=agent_run_id, 
    session_id=thread_id,
    metadata={"project_id": project_id, "instance_id": instance_id}
)
```

### 11.2 结构化日志

所有上下文信息自动包含在日志中：

```python
logger.info(f"Starting agent run")  # 自动包含 request_id, thread_id 等
```

## 12. 总结

Suna 的上下文管理系统通过分层架构实现了：

1. **业务层面**：通过 ContextManager 管理对话上下文，防止 token 溢出
2. **系统层面**：通过 contextvars 和中间件实现请求级别的上下文隔离
3. **分布式层面**：通过 Redis 实现跨进程的状态同步和控制
4. **性能优化**：通过连接池、批量操作和消息压缩提高效率
5. **可观测性**：通过结构化日志和分布式追踪提供完整的调试能力

这个系统为高并发的 AI 对话应用提供了稳定、高效、可扩展的基础设施。