# Suna "Hello" 消息处理时序图

## 完整时序图

```mermaid
sequenceDiagram
    participant U as 用户
    participant UI as 前端 UI
    participant API as FastAPI 后端
    participant DB as Supabase DB
    participant Q as Dramatiq 队列
    participant W as Worker 进程
    participant R as Redis
    participant LLM as LLM API
    participant SSE as SSE Stream

    U->>UI: 输入 "hello" 并按 Enter
    UI->>UI: handleSubmit() 处理输入
    
    UI->>DB: INSERT messages (user message)
    DB-->>UI: 返回 message_id
    
    UI->>API: POST /thread/{id}/agent/start
    Note over API: 验证权限、检查计费
    API->>DB: INSERT agent_runs
    DB-->>API: 返回 agent_run_id
    
    API->>Q: 发送异步任务
    API-->>UI: 返回 {agent_run_id}
    
    UI->>SSE: 建立 EventSource 连接
    Note over UI: 开始监听流式响应
    
    Q->>W: Worker 获取任务
    W->>DB: 加载对话历史
    DB-->>W: 返回消息列表
    
    W->>W: 构建 LLM 请求
    W->>LLM: 流式调用 completion API
    
    loop 流式响应
        LLM-->>W: 返回 token
        W->>R: PUBLISH 到 Redis 通道
        R->>SSE: 触发订阅事件
        SSE-->>UI: 推送 data chunk
        UI->>UI: 更新显示内容
    end
    
    W->>DB: UPDATE agent_runs (完成)
    W->>R: 存储完整响应
    
    SSE-->>UI: 发送完成信号
    UI->>UI: 显示完整回复
```

## 关键组件交互

### 1. 前端发起请求

```mermaid
graph LR
    A[用户输入] --> B[ChatInput 组件]
    B --> C[消息验证]
    C --> D[Supabase Client]
    D --> E[保存消息]
    E --> F[API 调用]
```

### 2. 后端处理流程

```mermaid
graph TD
    A[API 接收请求] --> B{权限验证}
    B -->|通过| C[创建 agent_run]
    B -->|失败| D[返回错误]
    C --> E[发送到队列]
    E --> F[返回 run_id]
    
    G[Worker 处理] --> H[加载上下文]
    H --> I[调用 LLM]
    I --> J[处理响应]
    J --> K[发布到 Redis]
```

### 3. 实时通信机制

```mermaid
graph LR
    A[Worker] -->|发布| B[Redis Pub/Sub]
    B --> C[SSE Handler]
    C -->|推送| D[EventSource]
    D --> E[前端 Hook]
    E --> F[UI 更新]
```

## 数据流动

### 消息数据结构

```typescript
// 用户消息
{
  id: "msg_123",
  thread_id: "thread_456",
  role: "user",
  content: "hello",
  created_at: "2024-01-01T10:00:00Z"
}

// Agent 响应
{
  type: "assistant_message",
  content: "Hello! How can I assist you today?",
  agent_run_id: "run_789"
}
```

### Redis 键值设计

```
stream:{agent_run_id}    # Pub/Sub 通道
response:{agent_run_id}  # 完整响应存储
status:{agent_run_id}    # 运行状态
```

## 性能优化点

1. **并发处理**
   - 多个 Worker 并行处理任务
   - Redis 连接池复用

2. **缓存策略**
   - 对话历史缓存
   - LLM 响应缓存

3. **流式优化**
   - 按需建立 SSE 连接
   - 自动重连机制

4. **资源管理**
   - 连接超时控制
   - 内存使用限制