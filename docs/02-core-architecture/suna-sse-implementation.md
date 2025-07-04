# Suna 项目 SSE 实时推送架构解析

## 概述

Suna 项目采用 Server-Sent Events (SSE) 技术实现了 AI Agent 执行过程的实时消息推送。本文档详细解析了前后端 SSE 连接的建立、消息流转机制以及异步任务结果的推送实现。

## 架构设计

### 核心组件

1. **前端**：React + TypeScript，使用 EventSource API
2. **后端**：FastAPI + Dramatiq，提供 SSE 端点
3. **消息中间件**：Redis (List + PubSub)
4. **任务队列**：Dramatiq + Redis

### 数据流架构图

```
┌─────────────┐     SSE连接      ┌─────────────┐     Redis通信    ┌─────────────┐
│   前端应用   │ <-------------> │  FastAPI    │ <-------------> │    Redis    │
│             │                  │  SSE端点    │                 │             │
└─────────────┘                  └─────────────┘                 └─────────────┘
                                        ↑                               ↑
                                        │                               │
                                        └───────────────────────────────┤
                                                                        │
                                 ┌─────────────┐                        │
                                 │  Dramatiq   │ ───────────────────────┘
                                 │ 后台任务    │
                                 └─────────────┘
```

## 前端实现

### 1. 核心 Hook - useAgentStream

`useAgentStream` 是管理 SSE 连接的核心 Hook，负责：
- 建立和维护 SSE 连接
- 处理实时消息流
- 管理 Agent 执行状态
- 错误处理和重连逻辑

```typescript
// frontend/src/hooks/useAgentStream.ts
export function useAgentStream(
  callbacks: AgentStreamCallbacks,
  threadId: string,
  setMessages: (messages: UnifiedMessage[]) => void,
): UseAgentStreamResult {
  // 状态管理
  const [status, setStatus] = useState<string>('idle');
  const [textContent, setTextContent] = useState<
    { content: string; sequence?: number }[]
  >([]);
  const [toolCall, setToolCall] = useState<ParsedContent | null>(null);
  
  // ... 实现细节
}
```

### 2. SSE 连接建立

```typescript
// frontend/src/lib/api.ts
export const streamAgent = (agentRunId: string, callbacks: {...}) => {
  // 创建 SSE 连接
  const url = new URL(`${API_URL}/agent-run/${agentRunId}/stream`);
  url.searchParams.append('token', session.access_token);
  const eventSource = new EventSource(url.toString());
  
  // 存储活跃的流连接
  activeStreams.set(agentRunId, eventSource);
  
  // 设置事件处理器
  eventSource.onmessage = (event) => {
    // 处理消息
  };
  
  eventSource.onerror = (error) => {
    // 错误处理
  };
  
  eventSource.onclose = () => {
    // 连接关闭处理
  };
}
```

### 3. 消息类型处理

前端处理三种主要消息类型：

```typescript
switch (message.type) {
  case 'assistant':
    // AI 助手消息，支持流式输出
    if (parsedMetadata.stream_status === 'chunk') {
      // 累积文本块
      setTextContent(prev => prev.concat({
        sequence: message.sequence,
        content: parsedContent.content
      }));
    }
    break;
    
  case 'tool':
    // 工具调用消息
    callbacks.onMessage(message);
    break;
    
  case 'status':
    // 状态更新消息
    handleStatusUpdate(parsedContent);
    break;
}
```

### 4. 连接生命周期管理

```typescript
// 活跃连接管理
const activeStreams = new Map<string, EventSource>();

// 非运行状态缓存（避免重复连接）
const nonRunningAgentRuns = new Set<string>();

// 启动流
const startStreaming = async (runId: string) => {
  // 1. 检查 Agent 状态
  const status = await getAgentStatus(runId);
  if (status.status !== 'running') {
    nonRunningAgentRuns.add(runId);
    return;
  }
  
  // 2. 建立 SSE 连接
  const cleanup = streamAgent(runId, callbacks);
  streamCleanupRef.current = cleanup;
};

// 停止流
const stopStreaming = async () => {
  if (streamCleanupRef.current) {
    streamCleanupRef.current();
    streamCleanupRef.current = null;
  }
};
```

## 后端实现

### 1. SSE 端点

```python
# backend/agent/api.py
@router.get("/agent-run/{agent_run_id}/stream")
async def stream_agent_run(
    agent_run_id: str,
    token: str = Query(...),
    account_id: str = Depends(get_account_id_from_token)
):
    """SSE endpoint for streaming agent run responses"""
    
    async def event_generator():
        try:
            # 1. 推送历史消息
            existing_responses = await redis_client.lrange(
                f"agent_run:{agent_run_id}:responses", 0, -1
            )
            
            for response in existing_responses:
                yield f"data: {response.decode()}\n\n"
            
            # 2. 订阅新消息
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"agent_run:{agent_run_id}:new_response")
            
            # 3. 实时推送新消息
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    
                    # 检查控制信号
                    if data == b"END_STREAM":
                        break
                    elif data == b"ERROR":
                        yield f"data: {json.dumps({'status': 'error'})}\n\n"
                        break
                    
                    yield f"data: {data.decode()}\n\n"
                    
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
```

### 2. 异步任务执行

```python
# backend/run_agent_background.py
@dramatiq.actor(
    queue_name="agent_runs",
    max_retries=0,
    time_limit=3600000  # 1 hour
)
def run_agent_background(
    agent_run_id: str,
    thread_id: str,
    account_id: str,
    prompt: str,
    agent_id: str,
    ...
):
    """在后台执行 Agent"""
    
    # 使用分布式锁防止重复执行
    lock_key = f"agent_run_lock:{agent_run_id}"
    lock = redis_client.lock(lock_key, timeout=3600)
    
    if not lock.acquire(blocking=False):
        logger.warning(f"Agent run {agent_run_id} is already being processed")
        return
    
    try:
        # 初始化线程管理器
        thread_manager = ThreadManager(agent_run_id, redis_client)
        
        # 处理消息流
        for chunk in response:
            if chunk.type == "content_block_delta":
                # 处理流式内容
                message_data = {
                    "type": "assistant",
                    "content": json.dumps({
                        "content": chunk.delta.text
                    }),
                    "metadata": json.dumps({
                        "stream_status": "chunk"
                    })
                }
                
                # 写入 Redis List（持久化）
                redis_client.rpush(
                    f"agent_run:{agent_run_id}:responses",
                    json.dumps(message_data)
                )
                
                # 发布到 PubSub（通知）
                redis_client.publish(
                    f"agent_run:{agent_run_id}:new_response",
                    json.dumps(message_data)
                )
    
    finally:
        lock.release()
```

### 3. Redis 双轨机制

#### Redis List - 消息存储
- **用途**：持久化存储所有消息
- **键格式**：`agent_run:{agent_run_id}:responses`
- **操作**：`RPUSH` 追加新消息，`LRANGE` 读取历史消息

#### Redis PubSub - 事件通知
- **用途**：实时通知新消息到达
- **频道格式**：`agent_run:{agent_run_id}:new_response`
- **特点**：发布即忘，不存储消息

### 4. 消息去重机制

通过时序分离避免消息重复：

```
时间轴 ────────────────────────────────────────────────>

Agent执行:   [消息1] → [消息2] → [消息3] → [消息4] → [消息5]
              ↓         ↓         ↓         ↓         ↓
Redis List:  [1]      [1,2]     [1,2,3]   [1,2,3,4] [1,2,3,4,5]
                         
SSE连接: ────────────────────── 连接建立 ─────────────────────
                                  ↓
推送历史:                       [1,2,3]
                                  ↓
订阅PubSub:                    开始监听
                                  ↓
新消息通知:                              [4]       [5]
                                          ↓         ↓
推送新消息:                              [4]       [5]
```

## 关键特性

### 1. 流式输出支持

Assistant 消息支持分块传输，确保用户能实时看到 AI 的思考过程：

```typescript
// 前端：累积并排序文本块
const orderedTextContent = useMemo(() => {
  return textContent
    .sort((a, b) => a.sequence - b.sequence)
    .reduce((acc, curr) => acc + curr.content, '');
}, [textContent]);
```

### 2. 状态同步

前后端状态映射：

| 前端状态 | 后端状态 | 说明 |
|---------|---------|------|
| idle | - | 初始状态 |
| connecting | - | 建立连接中 |
| streaming | running | 消息传输中 |
| completed | completed | 正常完成 |
| stopped | stopped | 用户中止 |
| failed/error | error | 执行错误 |

### 3. 错误处理

- **连接级错误**：自动重试，获取 Agent 最终状态
- **消息级错误**：通过 status 消息传递错误信息
- **认证错误**：刷新 token 或重新登录

### 4. 性能优化

1. **连接复用**：每个 Agent 运行实例只建立一个 SSE 连接
2. **增量推送**：避免重复传输历史消息
3. **缓存机制**：非运行状态的 Agent 不再尝试连接
4. **批量读取**：一次性获取所有历史消息

## 最佳实践

### 1. 前端使用建议

```typescript
// 使用 useAgentStream Hook
const {
  status,
  textContent,
  toolCall,
  error,
  startStreaming,
  stopStreaming
} = useAgentStream({
  onMessage: handleMessage,
  onStatusChange: handleStatusChange,
  onError: handleError,
  onClose: handleClose
}, threadId, setMessages);

// 启动流
await startStreaming(agentRunId);

// 停止流
await stopStreaming();
```

### 2. 后端扩展建议

- 使用 Redis Cluster 提高可扩展性
- 实现消息压缩减少带宽占用
- 添加心跳机制检测连接健康
- 实现消息过期清理机制

### 3. 监控要点

- SSE 连接数量
- Redis 内存使用
- 消息延迟
- 连接断开频率

## 总结

Suna 的 SSE 实现通过以下设计实现了高效可靠的实时消息推送：

1. **解耦架构**：Agent 执行与消息推送完全解耦
2. **双轨机制**：Redis List 保证可靠性，PubSub 保证实时性
3. **优雅降级**：连接断开可恢复，消息不丢失
4. **流式体验**：支持 AI 回复的逐字显示

这种设计为用户提供了流畅的实时交互体验，同时保证了系统的可靠性和可扩展性。