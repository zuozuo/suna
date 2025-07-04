# Suna 系统异步任务执行流程详解

## 一、核心架构组件

Suna 系统采用了现代化的异步任务处理架构，主要包含以下核心组件：

1. **消息队列**: Dramatiq + RabbitMQ
   - 用于任务的异步分发和执行
   - 支持任务重试和错误处理

2. **缓存和通信**: Redis
   - List 数据结构：持久化存储任务执行结果
   - Pub/Sub 机制：实时通知客户端新的响应

3. **实时推送**: Server-Sent Events (SSE)
   - 单向持久连接，服务器主动推送数据
   - 支持断线重连，确保数据完整性

4. **前端状态管理**: React Hooks + EventSource API
   - 统一的状态管理和更新机制
   - 优雅的错误处理和重连逻辑

## 二、异步任务执行流程

### 1. 任务触发阶段

当用户在前端发起请求时，后端 API 接收并创建任务：

```python
# backend/agent/api.py:552-602
@router.post("/agent/start")
async def start_agent(body: AgentStartRequest, ...):
    # 生成唯一的任务 ID
    agent_run_id = str(uuid.uuid4())
    
    # 在数据库中创建任务记录
    await client.table('agent_runs').insert({
        "id": agent_run_id,
        "thread_id": thread_id,
        "status": "running",
        ...
    }).execute()
    
    # 发送异步任务到 Dramatiq 消息队列
    run_agent_background.send(
        agent_run_id=agent_run_id,
        thread_id=thread_id,
        instance_id=instance_id,
        model_name=model_name,
        enable_thinking=body.enable_thinking,
        ...
    )
    
    # 立即返回任务 ID，不等待执行完成
    return {"agent_run_id": agent_run_id, "status": "running"}
```

### 2. 后台任务执行阶段

Dramatiq worker 从队列中获取任务并执行：

```python
# backend/run_agent_background.py:58-313
@dramatiq.actor
async def run_agent_background(
    agent_run_id: str,
    thread_id: str,
    instance_id: str,
    ...
):
    # 定义 Redis 键和通道
    response_list_key = f"agent_run:{agent_run_id}:responses"
    response_channel = f"agent_run:{agent_run_id}:new_response"
    control_channel = f"agent_run:{agent_run_id}:control"
    
    # 设置幂等性锁，防止重复执行
    run_lock_key = f"agent_run_lock:{agent_run_id}"
    lock_acquired = await redis.set(run_lock_key, instance_id, nx=True, ex=REDIS_KEY_TTL)
    
    if not lock_acquired:
        logger.info(f"Agent run {agent_run_id} already being processed")
        return
    
    # 订阅控制通道，支持中途停止
    pubsub = await redis.create_pubsub()
    await pubsub.subscribe(control_channel)
    
    # 执行 agent 并流式处理响应
    async for response in run_agent(...):
        if stop_signal_received:
            break
            
        # 将响应存入 Redis List
        response_json = json.dumps(response)
        await redis.rpush(response_list_key, response_json)
        
        # 发布通知到 Redis Pub/Sub
        await redis.publish(response_channel, "new")
        
        # 检查是否为终止状态
        if response.get('type') == 'status':
            status = response.get('status')
            if status in ['completed', 'failed', 'stopped']:
                break
    
    # 更新数据库状态
    await update_agent_run_status(client, agent_run_id, final_status)
    
    # 清理资源
    await redis.expire(response_list_key, REDIS_RESPONSE_LIST_TTL)
```

### 3. SSE 流式传输阶段

前端通过 SSE 连接实时获取任务执行结果：

```python
# backend/agent/api.py:765-955
@router.get("/agent-run/{agent_run_id}/stream")
async def stream_agent_run(agent_run_id: str, ...):
    response_list_key = f"agent_run:{agent_run_id}:responses"
    response_channel = f"agent_run:{agent_run_id}:new_response"
    control_channel = f"agent_run:{agent_run_id}:control"
    
    async def stream_generator():
        last_processed_index = -1
        
        # 步骤1: 获取并发送已有的响应
        initial_responses_json = await redis.lrange(response_list_key, 0, -1)
        if initial_responses_json:
            initial_responses = [json.loads(r) for r in initial_responses_json]
            for response in initial_responses:
                yield f"data: {json.dumps(response)}\n\n"
            last_processed_index = len(initial_responses) - 1
        
        # 步骤2: 检查任务状态
        run_status = await client.table('agent_runs').select('status').eq("id", agent_run_id).execute()
        if run_status.data[0]['status'] != 'running':
            yield f"data: {json.dumps({'type': 'status', 'status': 'completed'})}\n\n"
            return
        
        # 步骤3: 订阅新响应通知
        pubsub_response = await redis.create_pubsub()
        await pubsub_response.subscribe(response_channel)
        
        pubsub_control = await redis.create_pubsub()
        await pubsub_control.subscribe(control_channel)
        
        # 步骤4: 实时推送新响应
        message_queue = asyncio.Queue()
        listener_task = asyncio.create_task(listen_messages())
        
        while not terminate_stream:
            queue_item = await message_queue.get()
            
            if queue_item["type"] == "new_response":
                # 获取新响应
                new_start_index = last_processed_index + 1
                new_responses_json = await redis.lrange(response_list_key, new_start_index, -1)
                
                if new_responses_json:
                    new_responses = [json.loads(r) for r in new_responses_json]
                    for response in new_responses:
                        yield f"data: {json.dumps(response)}\n\n"
                    last_processed_index += len(new_responses)
            
            elif queue_item["type"] == "control":
                # 处理控制信号（停止、错误等）
                control_signal = queue_item["data"]
                yield f"data: {json.dumps({'type': 'status', 'status': control_signal})}\n\n"
                break
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*"
        }
    )
```

### 4. 前端接收处理阶段

前端使用 React Hook 管理 SSE 连接和状态：

```typescript
// frontend/src/hooks/useAgentStream.ts
export function useAgentStream(callbacks: AgentStreamCallbacks, threadId: string) {
    const [status, setStatus] = useState<string>('idle');
    const [textContent, setTextContent] = useState<{content: string; sequence?: number}[]>([]);
    const [toolCall, setToolCall] = useState<ParsedContent | null>(null);
    
    const startStreaming = useCallback(async (runId: string) => {
        // 检查任务状态
        const agentStatus = await getAgentStatus(runId);
        if (agentStatus.status !== 'running') {
            finalizeStream(mapAgentStatus(agentStatus.status), runId);
            return;
        }
        
        // 建立 SSE 连接
        const cleanup = streamAgent(runId, {
            onMessage: handleStreamMessage,
            onError: handleStreamError,
            onClose: handleStreamClose
        });
        streamCleanupRef.current = cleanup;
    }, [...]);
    
    const handleStreamMessage = useCallback((rawData: string) => {
        // 解析消息
        const message = JSON.parse(rawData);
        
        switch (message.type) {
            case 'assistant':
                // 处理助手消息
                if (parsedMetadata.stream_status === 'chunk') {
                    // 累积流式文本块
                    setTextContent(prev => prev.concat({
                        sequence: message.sequence,
                        content: parsedContent.content
                    }));
                    callbacks.onAssistantChunk?.({ content: parsedContent.content });
                } else if (parsedMetadata.stream_status === 'complete') {
                    // 完整消息，清空缓冲区
                    setTextContent([]);
                    callbacks.onMessage(message);
                }
                break;
                
            case 'tool':
                // 处理工具调用
                setToolCall(null);
                callbacks.onMessage(message);
                break;
                
            case 'status':
                // 处理状态消息
                switch (parsedContent.status_type) {
                    case 'tool_started':
                        setToolCall({
                            role: 'assistant',
                            status_type: 'tool_started',
                            name: parsedContent.function_name,
                            arguments: parsedContent.arguments,
                        });
                        break;
                    case 'error':
                        setError(parsedContent.message);
                        finalizeStream('error', currentRunIdRef.current);
                        break;
                }
                break;
        }
    }, [...]);
    
    return {
        status,
        textContent: orderedTextContent,
        toolCall,
        error,
        agentRunId,
        startStreaming,
        stopStreaming,
    };
}
```

## 三、完整数据流程图

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │     │  Backend    │     │   Redis     │     │   Workers   │
│   (React)   │     │   (API)     │     │             │     │ (Dramatiq)  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                    │                    │
       │ 1. POST /start    │                    │                    │
       ├──────────────────>│                    │                    │
       │                   │                    │                    │
       │                   │ 2. Create Record   │                    │
       │                   ├───────────────────>│                    │
       │                   │                    │                    │
       │ 3. agent_run_id   │                    │                    │
       │<──────────────────┤                    │                    │
       │                   │                    │                    │
       │                   │ 4. Send to Queue   │                    │
       │                   ├────────────────────┼───────────────────>│
       │                   │                    │                    │
       │ 5. GET /stream    │                    │                    │
       ├──────────────────>│                    │                    │
       │                   │                    │                    │
       │                   │ 6. Get Initial     │                    │
       │                   ├───────────────────>│                    │
       │                   │                    │                    │
       │ 7. SSE Headers    │                    │                    │
       │<──────────────────┤                    │                    │
       │                   │                    │                    │
       │ 8. Initial Data   │                    │                    │
       │<──────────────────┤                    │                    │
       │                   │                    │                    │
       │                   │ 9. Subscribe       │                    │ 10. Execute Agent
       │                   ├───────────────────>│                    ├─────┐
       │                   │                    │                    │     │
       │                   │                    │<───────────────────┤<────┘
       │                   │                    │ 11. RPUSH Response │
       │                   │                    │                    │
       │                   │                    │<───────────────────┤
       │                   │                    │ 12. PUBLISH Event  │
       │                   │                    │                    │
       │                   │ 13. Notify         │                    │
       │                   │<───────────────────┤                    │
       │                   │                    │                    │
       │ 14. Stream Data   │                    │                    │
       │<──────────────────┤                    │                    │
       │                   │                    │                    │
       │                   │ (Repeat 10-14 for each response)      │
       │                   │                    │                    │
       │                   │                    │<───────────────────┤
       │                   │                    │ 15. Final Status   │
       │                   │                    │                    │
       │ 16. End Stream    │                    │                    │
       │<──────────────────┤                    │                    │
       │                   │                    │                    │
```

## 四、关键特性说明

### 1. 幂等性保证

系统使用 Redis 的 `SET NX` 操作实现分布式锁，确保同一任务不会被多个 worker 重复执行：

```python
run_lock_key = f"agent_run_lock:{agent_run_id}"
lock_acquired = await redis.set(run_lock_key, instance_id, nx=True, ex=REDIS_KEY_TTL)
```

### 2. 实时性保证

- **Redis Pub/Sub**: 消息发布后立即通知所有订阅者
- **SSE 长连接**: 保持持久连接，服务器主动推送
- **消息队列**: 使用 asyncio.Queue 协调多个异步监听器

### 3. 可靠性设计

- **持久化存储**: 所有响应存储在 Redis List 中，支持断线重连后恢复
- **TTL 管理**: 自动清理过期数据，默认保留 24 小时
- **错误处理**: 多层错误捕获和恢复机制

### 4. 可扩展性

- **多实例支持**: 通过 instance_id 区分不同的后端实例
- **并发处理**: 支持多个任务同时执行
- **资源隔离**: 每个任务使用独立的 Redis 键空间

### 5. 优雅停止

系统支持在任务执行过程中优雅停止：

```python
# 发送停止信号
await redis.publish(control_channel, "STOP")

# Worker 监听停止信号
if stop_signal_received:
    logger.info(f"Agent run {agent_run_id} stopped by signal.")
    final_status = "stopped"
    break
```

## 五、性能优化

1. **批量操作**: 使用 Redis pipeline 减少网络往返
2. **消息压缩**: 对大型响应进行压缩传输
3. **连接复用**: 复用 Redis 连接池
4. **异步并发**: 充分利用 Python asyncio 特性

## 六、监控和调试

系统提供了完善的日志记录：

```python
# 结构化日志
structlog.contextvars.bind_contextvars(
    agent_run_id=agent_run_id,
    thread_id=thread_id,
    request_id=request_id,
)

# 性能监控
duration = (datetime.now(timezone.utc) - start_time).total_seconds()
logger.info(f"Agent run completed (duration: {duration:.2f}s, responses: {total_responses})")
```

## 七、故障恢复

1. **断线重连**: 前端自动重新建立 SSE 连接
2. **状态恢复**: 从 Redis 恢复已有响应
3. **任务重试**: Dramatiq 自动重试失败任务
4. **数据完整性**: 使用事务确保状态一致性