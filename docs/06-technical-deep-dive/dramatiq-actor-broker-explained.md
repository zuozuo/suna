# Dramatiq 核心概念详解：Actor 和 Broker

## 🎭 Actor（演员/角色）

**Actor** 是 Dramatiq 中可以异步执行的函数。它就像一个"演员"，等待被调用来执行特定的任务。

### 定义和特点

#### 1. 装饰器模式
```python
@dramatiq.actor
def send_email(recipient, subject, body):
    # 这个函数现在是一个 Actor
    print(f"Sending email to {recipient}")
```

#### 2. 异步执行能力
```python
# 普通函数调用（同步执行）
send_email("user@example.com", "Hi", "Hello")  # 阻塞直到完成

# Actor 调用（异步执行）
send_email.send("user@example.com", "Hi", "Hello")  # 立即返回
```

#### 3. 配置选项
```python
@dramatiq.actor(
    max_retries=3,        # 最多重试3次
    min_backoff=1000,     # 最小重试间隔1秒（毫秒）
    priority=10,          # 优先级（数字越大优先级越高）
    time_limit=300000,    # 超时时间5分钟（毫秒）
    queue_name="high_priority"  # 指定队列名称
)
def process_video(video_id):
    # 处理视频的长时间任务
    pass
```

### Actor 的生命周期

```mermaid
graph LR
    A[定义 Actor] --> B["调用 .send()"]
    B --> C[创建 Message]
    C --> D[发送到 Broker]
    D --> E[Worker 执行]
    E --> F[任务完成]
```

### Actor 的高级用法

#### 1. 带参数发送
```python
# 延迟执行
process_order.send_with_options(
    args=(order_id,),
    delay=60000  # 延迟1分钟执行
)

# 设置优先级
urgent_task.send_with_options(
    priority=100  # 高优先级
)
```

#### 2. 获取结果（需要结果后端）
```python
from dramatiq.results import Results
from dramatiq.results.backends import RedisBackend

# 配置结果后端
backend = RedisBackend()
broker.add_middleware(Results(backend=backend))

@dramatiq.actor(store_results=True)
def calculate(x, y):
    return x + y

# 获取结果
message = calculate.send(5, 3)
result = backend.get_result(message, block=True, timeout=5000)
print(result)  # 8
```

## 📮 Broker（代理/中间人）

**Broker** 是消息队列的抽象接口，负责在 Actor 和 Worker 之间传递消息。它就像一个"邮局"，接收和分发任务。

### Broker 的核心职责

#### 1. 消息存储
- 接收来自应用的任务消息
- 安全地存储消息直到被处理
- 保证消息持久化（即使系统重启）

#### 2. 消息分发
- 将消息分发给可用的 Worker
- 负载均衡
- 确保消息只被处理一次

#### 3. 可靠性保证
- 消息确认机制
- 失败重试
- 死信队列（处理无法执行的消息）

### Dramatiq 支持的 Broker 类型

#### 1. RabbitMQ Broker（生产环境推荐）

```python
from dramatiq.brokers.rabbitmq import RabbitmqBroker

# 基本配置
broker = RabbitmqBroker(
    host="localhost",
    port=5672
)

# 完整配置
broker = RabbitmqBroker(
    url="amqp://user:password@localhost:5672/vhost",
    confirm_delivery=True,      # 确认消息投递
    connection_attempts=5,      # 连接重试次数
    max_priority=10,           # 支持的最大优先级
    middleware=[               # 中间件
        dramatiq.middleware.AgeLimit(),
        dramatiq.middleware.TimeLimit(),
        dramatiq.middleware.Callbacks(),
        dramatiq.middleware.Retries(),
    ]
)

dramatiq.set_broker(broker)
```

**RabbitMQ 优势**：
- ✅ 高可靠性和持久性
- ✅ 支持集群和高可用
- ✅ 丰富的路由功能
- ✅ 成熟的管理工具
- ✅ 支持优先级队列

#### 2. Redis Broker（开发环境）

```python
from dramatiq.brokers.redis import RedisBroker

# 基本配置
broker = RedisBroker(
    host="localhost",
    port=6379,
    db=0
)

# 带密码和连接池
broker = RedisBroker(
    url="redis://password@localhost:6379/0",
    namespace="dramatiq",      # 键前缀
    connection_pool_kwargs={
        "max_connections": 20
    }
)

dramatiq.set_broker(broker)
```

**Redis 优势**：
- ✅ 简单易用
- ✅ 轻量级
- ✅ 开发环境友好
- ⚠️ 持久性较弱
- ⚠️ 不支持真正的优先级队列

### Broker 的工作原理

```mermaid
graph TD
    A[应用程序] -->|"1. actor.send()"| B[Broker]
    B -->|"2. 存储消息"| C[消息队列]
    C -->|"3. 分发消息"| D[Worker 1]
    C -->|"3. 分发消息"| E[Worker 2]
    C -->|"3. 分发消息"| F[Worker 3]
    D -->|"4. 确认完成"| C
    E -->|"4. 确认完成"| C
    F -->|"4. 确认完成"| C
```

## 🔄 Actor 和 Broker 的协作

### 完整的工作流程示例

```python
# === 配置文件 config.py ===
import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker

# 1. 创建和配置 Broker
broker = RabbitmqBroker(
    host="localhost",
    middleware=[
        dramatiq.middleware.AgeLimit(),
        dramatiq.middleware.TimeLimit(),
        dramatiq.middleware.Callbacks(),
        dramatiq.middleware.Retries(max_retries=3),
        dramatiq.middleware.AsyncIO(),  # 支持异步 actor
    ]
)

# 2. 设置为默认 Broker
dramatiq.set_broker(broker)

# === 任务定义 tasks.py ===
import dramatiq
import time

# 3. 定义 Actors
@dramatiq.actor(queue_name="emails", priority=5)
def send_email(recipient, subject, body):
    """发送邮件的 Actor"""
    print(f"Sending email to {recipient}")
    # 模拟发送邮件
    time.sleep(2)
    print(f"Email sent to {recipient}")

@dramatiq.actor(queue_name="orders", priority=10, max_retries=5)
def process_order(order_id):
    """处理订单的 Actor"""
    print(f"Processing order {order_id}")
    # 订单处理逻辑
    time.sleep(5)
    if random.random() < 0.1:  # 10% 失败率
        raise Exception("Order processing failed")
    return f"Order {order_id} completed"

@dramatiq.actor(time_limit=600000)  # 10分钟超时
async def generate_report(report_type, date_range):
    """生成报告的异步 Actor"""
    print(f"Generating {report_type} report")
    # 异步 I/O 操作
    await fetch_data(date_range)
    await process_data()
    await save_report()
    print("Report generated")

# === 应用代码 app.py ===
from tasks import send_email, process_order, generate_report

# 4. 发送任务到 Broker
def handle_user_request():
    # 立即返回，任务在后台执行
    send_email.send(
        "customer@example.com",
        "Order Confirmation",
        "Your order has been received"
    )
    
    # 延迟执行
    process_order.send_with_options(
        args=(12345,),
        delay=10000  # 10秒后执行
    )
    
    # 高优先级任务
    generate_report.send_with_options(
        args=("sales", "2024-01"),
        priority=50
    )

# === Worker 启动 ===
# 5. 在终端启动 Worker 处理任务
# dramatiq tasks:send_email tasks:process_order tasks:generate_report
```

### Actor 和 Broker 的交互细节

1. **消息创建**
   ```python
   # 当调用 actor.send() 时
   message = Message(
       queue_name="default",
       actor_name="send_email",
       args=("user@example.com", "Hi", "Hello"),
       kwargs={},
       options={
           "message_id": "uuid-here",
           "message_timestamp": 1234567890,
       }
   )
   ```

2. **Broker 处理**
   ```python
   # Broker 接收消息
   broker.enqueue(message)
   # 消息被序列化并存储到队列
   # RabbitMQ: 持久化到磁盘
   # Redis: 存储到内存（可选持久化）
   ```

3. **Worker 消费**
   ```python
   # Worker 从 Broker 获取消息
   message = broker.consume(queue_name="default")
   # 查找对应的 Actor
   actor = registry.get_actor(message.actor_name)
   # 执行 Actor
   result = actor(*message.args, **message.kwargs)
   # 确认消息已处理
   broker.ack(message)
   ```

## 🍳 形象的比喻：餐厅系统

把 Dramatiq 系统想象成一个高效的餐厅：

### 餐厅组件对应关系

| Dramatiq 组件 | 餐厅比喻 | 功能说明 |
|--------------|---------|---------|
| **Actor** | 厨师 | 每个厨师专门做某类菜（特定任务） |
| **Broker** | 订单系统 | 接收和分配订单 |
| **Message** | 订单票 | 包含菜品详情和要求 |
| **Worker** | 厨房 | 厨师工作的地方 |
| **Queue** | 订单队列 | 不同类型订单的等待列表 |

### 工作流程

1. **顾客点餐**（应用发送任务）
   ```python
   cook_pasta.send("spaghetti", "carbonara")  # 下单
   ```

2. **订单系统记录**（Broker 存储消息）
   - 订单被打印并放入队列
   - 按优先级排序（VIP 订单优先）

3. **厨师接单**（Worker 获取任务）
   - 空闲的厨师从订单队列取单
   - 开始制作菜品

4. **完成通知**（任务完成）
   - 菜品完成，通知服务员
   - 订单标记为完成

## 🚀 在 Suna 中的实际应用

### Suna 的 Actor 定义

```python
# 三个主要的 Actor 对应不同类型的任务

@dramatiq.actor
async def run_agent_background(
    agent_run_id: str,
    thread_id: str,
    model_name: str,
    # ...
):
    """
    处理 AI 对话的 Actor
    - 可能运行几分钟到几小时
    - 需要流式返回结果
    - 支持中途停止
    """
    pass

@dramatiq.actor
async def run_workflow_background(
    execution_id: str,
    workflow_definition: Dict,
    # ...
):
    """
    执行工作流的 Actor
    - 协调多个步骤
    - 可能调用其他服务
    - 需要状态追踪
    """
    pass

@dramatiq.actor
async def check_health(key: str):
    """
    健康检查的 Actor
    - 轻量级任务
    - 快速执行
    - 用于监控
    """
    await redis.set(key, "healthy", ex=60)
```

### Suna 的 Broker 配置

```python
# 使用 RabbitMQ 作为生产环境 Broker
rabbitmq_broker = RabbitmqBroker(
    host=os.getenv('RABBITMQ_HOST', 'rabbitmq'),
    port=5672,
    middleware=[
        dramatiq.middleware.AsyncIO(),  # 关键：支持异步 Actor
        # 其他中间件...
    ]
)

dramatiq.set_broker(rabbitmq_broker)
```

### 为什么这种设计对 Suna 很重要

1. **非阻塞 API**
   - 用户发送消息后立即得到响应
   - AI 处理在后台进行

2. **可扩展性**
   - 可以运行多个 Worker 处理并发请求
   - 简单地增加 Worker 数量即可扩容

3. **可靠性**
   - 即使 Worker 崩溃，消息不会丢失
   - 自动重试失败的任务

4. **实时反馈**
   - 配合 Redis 实现流式响应
   - 用户可以看到 AI 的实时输出

这种 Actor-Broker 模式让 Suna 能够优雅地处理复杂的 AI 任务，同时保持系统的响应性和可靠性。