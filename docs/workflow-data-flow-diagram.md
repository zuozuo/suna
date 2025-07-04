# Suna Workflow 数据流详细图解

## 1. 工作流创建数据流

```mermaid
flowchart TB
    subgraph "用户界面层"
        UI[用户拖拽节点] --> WB[WorkflowBuilder]
        WB --> RF[ReactFlow Canvas]
    end
    
    subgraph "前端数据处理"
        RF --> NS[节点状态管理]
        RF --> ES[边状态管理]
        NS --> AS[自动保存检测]
        ES --> AS
        AS -->|2秒延迟| API1[调用保存API]
    end
    
    subgraph "API 层"
        API1 --> VAL[数据验证]
        VAL --> CONV[WorkflowConverter]
        CONV --> WD[生成 WorkflowDefinition]
    end
    
    subgraph "数据存储"
        WD --> DB1[(workflows 表)]
        API1 --> DB2[(workflow_flows 表)]
        DB1 --> |定义数据| DEF[步骤/触发器/配置]
        DB2 --> |可视化数据| VIS[节点/边/位置]
    end
    
    style UI fill:#e1f5fe
    style WB fill:#e1f5fe
    style RF fill:#e1f5fe
    style DB1 fill:#fff3e0
    style DB2 fill:#fff3e0
```

## 2. 工作流执行数据流 - 传统模式

```mermaid
flowchart LR
    subgraph "触发阶段"
        T1[手动触发] --> EX[执行请求]
        T2[定时触发] --> EX
        T3[Webhook触发] --> EX
    end
    
    subgraph "执行准备"
        EX --> L1[加载工作流定义]
        L1 --> L2[加载可视化数据]
        L2 --> EXT[提取配置]
        EXT --> TOOLS[工具列表]
        EXT --> MCPS[MCP配置]
        EXT --> PROMPT[系统提示词]
    end
    
    subgraph "Agent 执行"
        TOOLS --> AC[构建Agent配置]
        MCPS --> AC
        PROMPT --> AC
        AC --> AGENT[运行Agent]
        AGENT --> SAND[沙箱环境]
    end
    
    subgraph "结果处理"
        AGENT --> R1[执行结果]
        R1 --> REDIS[(Redis队列)]
        REDIS --> SSE[SSE流式推送]
        SSE --> CLIENT[客户端]
    end
    
    style T1 fill:#c8e6c9
    style T2 fill:#c8e6c9
    style T3 fill:#c8e6c9
    style REDIS fill:#ffccbc
    style CLIENT fill:#e1f5fe
```

## 3. 工作流执行数据流 - 确定性模式

```mermaid
flowchart TB
    subgraph "初始化"
        START[开始执行] --> LOAD[加载工作流]
        LOAD --> BUILD[构建执行图]
        BUILD --> DETECT[检测循环]
    end
    
    subgraph "执行图构建"
        BUILD --> G1[节点依赖分析]
        BUILD --> G2[入口点识别]
        BUILD --> G3[拓扑排序]
        DETECT --> LOOP[循环状态管理]
    end
    
    subgraph "节点执行循环"
        G3 --> QUEUE[执行队列]
        QUEUE --> CHECK{检查依赖}
        CHECK -->|满足| EXEC[执行节点]
        CHECK -->|不满足| QUEUE
        
        EXEC --> TYPE{节点类型}
        TYPE -->|Input| IN[处理输入]
        TYPE -->|Agent| AG[执行Agent]
        TYPE -->|Tool| TL[配置工具]
        TYPE -->|MCP| MC[配置MCP]
        
        IN --> OUT[节点输出]
        AG --> OUT
        TL --> OUT
        MC --> OUT
        
        OUT --> CTX[更新上下文]
        CTX --> NEXT[激活后续节点]
        NEXT --> QUEUE
    end
    
    subgraph "循环处理"
        EXEC --> LC{在循环中?}
        LC -->|是| ITER[更新迭代]
        ITER --> EXIT{退出条件?}
        EXIT -->|否| QUEUE
        EXIT -->|是| BREAK[跳出循环]
    end
    
    style START fill:#c8e6c9
    style QUEUE fill:#fff3e0
    style OUT fill:#e1f5fe
```

## 4. 节点间数据传递机制

```mermaid
flowchart LR
    subgraph "源节点"
        N1[节点A] --> O1[输出数据]
        O1 --> H1[输出句柄]
    end
    
    subgraph "连接"
        H1 --> E1[边Edge]
        E1 --> H2[输入句柄]
    end
    
    subgraph "目标节点"
        H2 --> I1[输入数据]
        I1 --> N2[节点B]
        N2 --> PROC[处理数据]
    end
    
    subgraph "数据转换"
        O1 --> T1[类型转换]
        T1 --> T2[格式适配]
        T2 --> I1
    end
    
    style N1 fill:#e1f5fe
    style N2 fill:#e1f5fe
    style E1 fill:#fff3e0
```

## 5. 工具和 MCP 配置数据流

```mermaid
flowchart TB
    subgraph "配置来源"
        S1[可视化节点配置] --> MERGE
        S2[工作流步骤配置] --> MERGE
        S3[Agent 默认工具] --> MERGE
    end
    
    subgraph "配置处理"
        MERGE[合并配置] --> DEDUP[去重处理]
        DEDUP --> CRED[加载凭证]
        CRED --> VALID[验证配置]
    end
    
    subgraph "凭证管理"
        CRED --> CM[CredentialManager]
        CM --> PROF[获取配置文件]
        PROF --> DEC[解密凭证]
        DEC --> CRED
    end
    
    subgraph "最终配置"
        VALID --> TOOLS[启用的工具集]
        VALID --> MCPS[MCP服务器列表]
        TOOLS --> AGENT[Agent配置]
        MCPS --> AGENT
    end
    
    style S1 fill:#c8e6c9
    style S2 fill:#c8e6c9
    style S3 fill:#c8e6c9
    style AGENT fill:#e1f5fe
```

## 6. 实时状态同步数据流

```mermaid
sequenceDiagram
    participant Browser as 浏览器
    participant Frontend as 前端
    participant API as API服务
    participant Redis as Redis
    participant Executor as 执行器
    participant DB as 数据库
    
    Browser->>Frontend: 发起执行
    Frontend->>API: POST /execute
    API->>DB: 创建执行记录
    API->>Redis: 初始化队列
    API->>Executor: 启动异步执行
    API-->>Frontend: 返回执行ID
    
    Frontend->>API: GET /stream/{id}
    API->>Redis: 订阅频道
    
    loop 执行过程
        Executor->>DB: 更新状态
        Executor->>Redis: 推送进度
        Redis-->>API: 消息通知
        API-->>Frontend: SSE推送
        Frontend-->>Browser: 更新UI
    end
    
    Executor->>Redis: 发送完成信号
    Redis-->>API: 完成通知
    API-->>Frontend: 关闭流
```

## 7. 错误处理和恢复数据流

```mermaid
flowchart TB
    subgraph "错误检测"
        EXEC[节点执行] --> ERR{发生错误?}
        ERR -->|是| ETYPE{错误类型}
        ERR -->|否| CONT[继续执行]
    end
    
    subgraph "错误分类"
        ETYPE -->|超时| TIMEOUT[执行超时]
        ETYPE -->|异常| EXCEPT[运行异常]
        ETYPE -->|资源| RESOURCE[资源限制]
        ETYPE -->|网络| NETWORK[网络错误]
    end
    
    subgraph "错误处理"
        TIMEOUT --> RETRY{重试?}
        EXCEPT --> LOG[记录日志]
        RESOURCE --> CLEAN[清理资源]
        NETWORK --> RETRY
        
        RETRY -->|是| EXEC
        RETRY -->|否| FAIL[标记失败]
        LOG --> FAIL
        CLEAN --> FAIL
    end
    
    subgraph "恢复机制"
        FAIL --> SAVE[保存状态]
        SAVE --> NOTIFY[通知用户]
        NOTIFY --> RESUME{恢复执行?}
        RESUME -->|是| RESTORE[恢复状态]
        RESTORE --> EXEC
    end
    
    style ERR fill:#ffccbc
    style FAIL fill:#ffccbc
    style CONT fill:#c8e6c9
```

## 8. 数据持久化和缓存策略

```mermaid
flowchart LR
    subgraph "数据层级"
        L1[内存缓存] --> L2[Redis缓存]
        L2 --> L3[数据库持久化]
    end
    
    subgraph "写入策略"
        W1[实时数据] -->|直接| L1
        W2[状态数据] -->|异步| L2
        W3[结果数据] -->|批量| L3
    end
    
    subgraph "读取策略"
        R1[热数据] -->|优先| L1
        R2[温数据] -->|次优| L2
        R3[冷数据] -->|最后| L3
    end
    
    subgraph "缓存更新"
        L3 -->|预加载| L2
        L2 -->|LRU| L1
        L1 -->|过期| EVICT[清除]
    end
    
    style L1 fill:#e1f5fe
    style L2 fill:#fff3e0
    style L3 fill:#ffccbc
```

## 总结

Suna Workflow 系统的数据流设计体现了以下特点：

1. **分层清晰**：前端展示层、业务逻辑层、数据存储层职责明确
2. **异步处理**：大量使用异步模式，提高系统响应性
3. **流式传输**：执行结果实时推送，用户体验良好
4. **容错机制**：完善的错误处理和恢复策略
5. **性能优化**：多级缓存和批量处理提升性能

这种设计确保了系统的高可用性、可扩展性和良好的用户体验。