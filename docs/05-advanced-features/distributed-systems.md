# Suna 分布式系统设计

## 概述

Suna 的分布式架构设计支持从单机部署到大规模集群部署的平滑过渡。系统通过消息队列、分布式锁、缓存等机制实现了高可用、高性能的分布式服务。

## 分布式架构核心组件

### 1. 任务分发系统

基于 Dramatiq + RabbitMQ 的分布式任务队列：

```python
# 任务定义
@dramatiq.actor(queue_name="agent_tasks")
async def run_agent_background(
    agent_run_id: str,
    thread_id: str,
    **kwargs
):
    # 任务可以在任意 Worker 节点执行
    pass
```

**特性**：
- 自动负载均衡
- 任务重试机制
- 死信队列处理
- 优先级队列支持

### 2. 分布式锁机制

基于 Redis 的分布式锁实现：

```python
class RedisLock:
    def __init__(self, redis_client, key: str, timeout: int = 30):
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.identifier = str(uuid.uuid4())
    
    async def acquire(self) -> bool:
        """获取锁"""
        return await self.redis.set(
            self.key, 
            self.identifier,
            nx=True,  # 仅在不存在时设置
            ex=self.timeout
        )
    
    async def release(self):
        """释放锁（使用 Lua 脚本保证原子性）"""
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        await self.redis.eval(lua_script, 1, self.key, self.identifier)
```

**应用场景**：
- 防止任务重复执行
- 资源独占访问
- 分布式事务协调

详见：[分布式锁实现](../06-technical-deep-dive/distributed-lock-implementation.md)

### 3. 服务发现与注册

```python
class ServiceRegistry:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.service_key = "services:{service_type}"
        self.heartbeat_interval = 30
    
    async def register(self, service_type: str, instance_id: str, metadata: dict):
        """注册服务实例"""
        key = self.service_key.format(service_type=service_type)
        await self.redis.hset(
            key,
            instance_id,
            json.dumps({
                "metadata": metadata,
                "last_heartbeat": time.time()
            })
        )
    
    async def discover(self, service_type: str) -> List[ServiceInstance]:
        """发现可用服务"""
        key = self.service_key.format(service_type=service_type)
        instances = await self.redis.hgetall(key)
        
        active_instances = []
        for instance_id, data in instances.items():
            info = json.loads(data)
            # 检查心跳是否超时
            if time.time() - info["last_heartbeat"] < self.heartbeat_interval * 2:
                active_instances.append(ServiceInstance(instance_id, info["metadata"]))
        
        return active_instances
```

### 4. 分布式缓存

多级缓存架构：

```
┌─────────────────┐
│   本地缓存      │ (进程内 LRU Cache)
└────────┬────────┘
         │
┌────────▼────────┐
│   Redis 缓存    │ (共享缓存层)
└────────┬────────┘
         │
┌────────▼────────┐
│    数据库       │ (持久化存储)
└─────────────────┘
```

```python
class DistributedCache:
    def __init__(self, redis_client, local_cache_size=1000):
        self.redis = redis_client
        self.local_cache = LRUCache(maxsize=local_cache_size)
    
    async def get(self, key: str) -> Optional[Any]:
        # 1. 尝试本地缓存
        if key in self.local_cache:
            return self.local_cache[key]
        
        # 2. 尝试 Redis 缓存
        value = await self.redis.get(key)
        if value:
            self.local_cache[key] = value
            return json.loads(value)
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        # 同时更新两级缓存
        self.local_cache[key] = value
        await self.redis.setex(key, ttl, json.dumps(value))
```

## 高可用设计

### 1. 服务冗余

```yaml
# Kubernetes 部署示例
apiVersion: apps/v1
kind: Deployment
metadata:
  name: suna-backend-api
spec:
  replicas: 3  # API 服务 3 副本
  selector:
    matchLabels:
      app: suna-backend-api
  template:
    spec:
      containers:
      - name: api
        image: suna-backend:latest
        env:
        - name: REDIS_SENTINEL_HOSTS
          value: "sentinel-1:26379,sentinel-2:26379,sentinel-3:26379"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: suna-backend-worker
spec:
  replicas: 5  # Worker 服务 5 副本
  selector:
    matchLabels:
      app: suna-backend-worker
  template:
    spec:
      containers:
      - name: worker
        image: suna-backend:latest
        command: ["dramatiq", "run_agent_background"]
```

### 2. 故障转移

Redis Sentinel 配置：

```conf
# sentinel.conf
port 26379
sentinel monitor mymaster redis-master 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel parallel-syncs mymaster 1
sentinel failover-timeout mymaster 10000
```

应用层故障处理：

```python
class ResilientRedisClient:
    def __init__(self, sentinel_hosts):
        self.sentinel = Sentinel(sentinel_hosts)
        
    async def get_master(self):
        """获取当前主节点连接"""
        return self.sentinel.master_for('mymaster', decode_responses=True)
    
    async def execute_with_retry(self, operation, *args, max_retries=3):
        """带重试的操作执行"""
        for attempt in range(max_retries):
            try:
                master = await self.get_master()
                return await getattr(master, operation)(*args)
            except (ConnectionError, TimeoutError) as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # 指数退避
```

### 3. 负载均衡

应用层负载均衡：

```python
class LoadBalancer:
    def __init__(self, instances: List[str]):
        self.instances = instances
        self.current = 0
        self.health_check_interval = 10
        self.healthy_instances = set(instances)
    
    def get_next_instance(self) -> Optional[str]:
        """轮询算法获取下一个健康实例"""
        if not self.healthy_instances:
            return None
        
        healthy_list = list(self.healthy_instances)
        instance = healthy_list[self.current % len(healthy_list)]
        self.current += 1
        return instance
    
    async def health_check(self):
        """定期健康检查"""
        while True:
            for instance in self.instances:
                if await self._check_instance_health(instance):
                    self.healthy_instances.add(instance)
                else:
                    self.healthy_instances.discard(instance)
            
            await asyncio.sleep(self.health_check_interval)
```

## 分布式事务处理

### 1. Saga 模式实现

```python
class SagaTransaction:
    def __init__(self):
        self.steps = []
        self.compensations = []
    
    def add_step(self, action, compensation):
        """添加事务步骤和补偿操作"""
        self.steps.append(action)
        self.compensations.append(compensation)
    
    async def execute(self):
        """执行事务"""
        completed_steps = []
        
        try:
            for i, step in enumerate(self.steps):
                result = await step()
                completed_steps.append(i)
        except Exception as e:
            # 执行补偿操作
            for i in reversed(completed_steps):
                try:
                    await self.compensations[i]()
                except Exception as comp_error:
                    logger.error(f"补偿操作失败: {comp_error}")
            raise e

# 使用示例
saga = SagaTransaction()
saga.add_step(
    action=lambda: create_agent_run(agent_run_id),
    compensation=lambda: delete_agent_run(agent_run_id)
)
saga.add_step(
    action=lambda: start_sandbox(sandbox_id),
    compensation=lambda: stop_sandbox(sandbox_id)
)
saga.add_step(
    action=lambda: bill_user(user_id, amount),
    compensation=lambda: refund_user(user_id, amount)
)

await saga.execute()
```

### 2. 分布式追踪

集成 OpenTelemetry：

```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# 配置追踪
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger",
    agent_port=6831,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# 使用追踪
class TracedThreadManager:
    @tracer.start_as_current_span("run_thread")
    async def run_thread(self, thread_id: str, **kwargs):
        span = trace.get_current_span()
        span.set_attribute("thread.id", thread_id)
        
        with tracer.start_as_current_span("get_messages"):
            messages = await self.get_messages(thread_id)
        
        with tracer.start_as_current_span("call_llm"):
            response = await self.call_llm(messages)
        
        return response
```

## 数据分片策略

### 1. 用户数据分片

```python
class ShardedDatabase:
    def __init__(self, shard_count: int = 4):
        self.shard_count = shard_count
        self.connections = {
            i: DatabaseConnection(f"shard_{i}")
            for i in range(shard_count)
        }
    
    def get_shard(self, user_id: str) -> DatabaseConnection:
        """基于用户 ID 的一致性哈希分片"""
        shard_id = hash(user_id) % self.shard_count
        return self.connections[shard_id]
    
    async def get_user_data(self, user_id: str):
        shard = self.get_shard(user_id)
        return await shard.query(
            "SELECT * FROM users WHERE user_id = %s",
            (user_id,)
        )
```

### 2. 时序数据分片

```python
class TimeSeriesSharding:
    def __init__(self):
        self.shards = {}
    
    def get_shard_key(self, timestamp: datetime) -> str:
        """按月分片"""
        return timestamp.strftime("%Y-%m")
    
    async def write_metric(self, metric_name: str, value: float, timestamp: datetime):
        shard_key = self.get_shard_key(timestamp)
        
        if shard_key not in self.shards:
            self.shards[shard_key] = await self.create_shard(shard_key)
        
        await self.shards[shard_key].insert({
            "metric": metric_name,
            "value": value,
            "timestamp": timestamp
        })
```

## 消息队列架构

### 1. 多队列设计

```python
# 队列配置
QUEUES = {
    "high_priority": {
        "max_priority": 10,
        "x-max-priority": 10
    },
    "agent_tasks": {
        "x-message-ttl": 3600000,  # 1小时 TTL
        "x-dead-letter-exchange": "dlx"
    },
    "batch_processing": {
        "x-max-length": 10000,
        "x-overflow": "reject-publish"
    }
}

# 任务路由
@dramatiq.actor(queue_name="high_priority", priority=10)
async def urgent_task():
    pass

@dramatiq.actor(queue_name="agent_tasks", time_limit=600000)
async def agent_task():
    pass

@dramatiq.actor(queue_name="batch_processing")
async def batch_task():
    pass
```

### 2. 消息可靠性保证

```python
class ReliableMessagePublisher:
    def __init__(self, channel):
        self.channel = channel
        self.unconfirmed = {}
        self.delivery_tag = 0
    
    async def publish_with_confirm(self, exchange, routing_key, message):
        """发布消息并等待确认"""
        self.delivery_tag += 1
        
        # 记录未确认消息
        self.unconfirmed[self.delivery_tag] = {
            "exchange": exchange,
            "routing_key": routing_key,
            "message": message,
            "timestamp": time.time()
        }
        
        # 发布消息
        await self.channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # 持久化
                message_id=str(self.delivery_tag)
            )
        )
        
        # 等待确认
        if not await self._wait_for_confirm(self.delivery_tag, timeout=5):
            # 重试或记录失败
            raise MessagePublishError("消息发布未确认")
```

## 监控与告警

### 1. 分布式指标收集

```python
from prometheus_client import Counter, Histogram, Gauge

# 定义指标
task_counter = Counter('suna_tasks_total', 'Total number of tasks', ['task_type', 'status'])
task_duration = Histogram('suna_task_duration_seconds', 'Task duration', ['task_type'])
active_agents = Gauge('suna_active_agents', 'Number of active agents')

# 使用指标
@task_duration.time()
async def run_agent_task():
    task_counter.labels(task_type='agent', status='started').inc()
    try:
        active_agents.inc()
        # 执行任务
        result = await execute_agent()
        task_counter.labels(task_type='agent', status='completed').inc()
        return result
    except Exception as e:
        task_counter.labels(task_type='agent', status='failed').inc()
        raise
    finally:
        active_agents.dec()
```

### 2. 分布式日志聚合

```python
import logging
from pythonjsonlogger import jsonlogger

# 配置结构化日志
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)

# 日志中间件
class DistributedLoggingMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        request_id = str(uuid.uuid4())
        
        # 注入请求 ID 到日志上下文
        with logger.contextvars.bind(
            request_id=request_id,
            service="api",
            instance_id=os.environ.get("INSTANCE_ID")
        ):
            logger.info("request_started", 
                       path=scope["path"],
                       method=scope["method"])
            
            try:
                await self.app(scope, receive, send)
                logger.info("request_completed", status="success")
            except Exception as e:
                logger.error("request_failed", error=str(e))
                raise
```

## 部署拓扑

### 1. 小规模部署（1-10 并发用户）

```
┌─────────────┐
│   单机部署   │
│  - Frontend │
│  - API      │
│  - Worker   │
│  - Redis    │
│  - RabbitMQ │
└─────────────┘
```

### 2. 中等规模部署（10-100 并发用户）

```
┌──────────────┐     ┌──────────────┐
│   Frontend   │     │   Frontend   │
└──────┬───────┘     └───────┬──────┘
       │                     │
    ┌──┴─────────────────────┴──┐
    │      Load Balancer        │
    └──┬─────────────────────┬──┘
       │                     │
┌──────▼───────┐     ┌───────▼──────┐
│     API      │     │     API      │
└──────────────┘     └──────────────┘
       │                     │
┌──────▼───────────────────────▼──────┐
│         Message Queue (RabbitMQ)     │
└──────┬───────────┬────────────┬─────┘
       │           │            │
┌──────▼─────┐ ┌───▼──────┐ ┌──▼──────┐
│  Worker 1  │ │ Worker 2 │ │Worker 3 │
└────────────┘ └──────────┘ └─────────┘
```

### 3. 大规模部署（100+ 并发用户）

完整的 Kubernetes 集群部署，包括：
- 多可用区部署
- 自动扩缩容
- 服务网格（Istio）
- 分布式存储
- 全链路监控

## 性能优化策略

### 1. 批处理优化

```python
class BatchProcessor:
    def __init__(self, batch_size=100, flush_interval=5):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer = []
        self.last_flush = time.time()
    
    async def add(self, item):
        self.buffer.append(item)
        
        if len(self.buffer) >= self.batch_size or \
           time.time() - self.last_flush > self.flush_interval:
            await self.flush()
    
    async def flush(self):
        if not self.buffer:
            return
        
        # 批量处理
        await self._process_batch(self.buffer)
        self.buffer = []
        self.last_flush = time.time()
```

### 2. 连接池优化

```python
# Redis 连接池
redis_pool = aioredis.ConnectionPool(
    host='redis',
    port=6379,
    db=0,
    max_connections=50,
    min_connections=10
)

# 数据库连接池
db_pool = asyncpg.create_pool(
    dsn='postgresql://user:pass@localhost/db',
    min_size=10,
    max_size=20,
    max_queries=50000,
    max_inactive_connection_lifetime=300
)
```

## 相关文档

- [异步任务架构](../02-core-architecture/async-task-architecture.md)
- [分布式锁实现](../06-technical-deep-dive/distributed-lock-implementation.md)
- [Dramatiq vs Celery](../06-technical-deep-dive/dramatiq-vs-celery.md)

## 总结

Suna 的分布式系统设计提供了：

1. **可扩展性**：从单机到集群的平滑过渡
2. **高可用性**：多副本、故障转移、自动恢复
3. **高性能**：分布式缓存、批处理、连接池
4. **可观测性**：分布式追踪、指标监控、日志聚合
5. **可靠性**：分布式事务、消息确认、数据一致性

这些设计确保了 Suna 能够应对各种规模的部署需求，提供稳定可靠的服务。