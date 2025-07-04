# Daytona 和 tmux 集成指南

## 概述

本文档介绍如何将 Daytona 开发环境与 tmux 会话管理结合使用，实现在云端开发环境中灵活执行和管理 shell 脚本的能力。

## Daytona 简介

Daytona 是一个开发环境管理平台，允许开发者快速创建、管理和访问云端开发工作区。主要特点：

- **工作区管理**：基于 Git 仓库创建隔离的开发环境
- **远程访问**：通过 SSH 访问工作区
- **环境一致性**：确保团队成员使用相同的开发环境
- **资源管理**：自动管理计算资源的分配和释放

## 集成架构

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Python 脚本    │────▶│  Daytona CLI     │────▶│  工作区实例     │
│  (控制层)      │     │  (daytona ssh)   │     │  (远程环境)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                                                 │
         │                                                 │
         ▼                                                 ▼
┌─────────────────┐                               ┌─────────────────┐
│  tmux 本地      │                               │  tmux 远程      │
│  (会话管理)     │                               │  (在工作区内)   │
└─────────────────┘                               └─────────────────┘
```

## Python 集成实现

### 1. DaytonaWorkspace 类

管理 Daytona 工作区的生命周期：

```python
class DaytonaWorkspace:
    """Daytona 工作区管理器"""
    
    def list_workspaces(self) -> List[Dict[str, Any]]:
        """列出所有工作区"""
        result = subprocess.run(
            ["daytona", "list", "--output", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    
    def create_workspace(self, name: str, git_url: str) -> bool:
        """创建新工作区"""
        subprocess.run(
            ["daytona", "create", name, "--git-url", git_url],
            check=True
        )
        return True
    
    def ssh_command(self, name: str, command: str) -> str:
        """在工作区中执行命令"""
        result = subprocess.run(
            ["daytona", "ssh", name, "--", command],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
```

### 2. TmuxSession 类

管理 tmux 会话的创建和交互：

```python
class TmuxSession:
    """tmux 会话管理器"""
    
    def create_session(self) -> bool:
        """创建 tmux 会话"""
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.session_name],
            check=True
        )
        return True
    
    def send_command(self, command: str) -> None:
        """发送命令到会话"""
        subprocess.run(
            ["tmux", "send-keys", "-t", self.session_name, command, "Enter"],
            check=True
        )
    
    def capture_output(self, start_line: int = -100) -> str:
        """捕获会话输出"""
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", self.session_name, "-p", "-S", str(start_line)],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
```

### 3. DaytonaTmuxExecutor 类

集成执行器，提供统一的接口：

```python
class DaytonaTmuxExecutor:
    """Daytona 和 tmux 集成执行器"""
    
    def setup_environment(self, workspace_name: str) -> bool:
        """设置执行环境"""
        # 启动 Daytona 工作区
        if not self.daytona.start_workspace(workspace_name):
            return False
        
        # 创建 tmux 会话
        session_name = f"daytona-{workspace_name}"
        self.tmux = TmuxSession(session_name)
        
        return self.tmux.create_session()
    
    def execute_script_with_monitoring(self, script_path: str) -> Dict[str, Any]:
        """执行脚本并实时监控"""
        # 发送执行命令
        self.tmux.send_command(f"bash {script_path}; echo '===SCRIPT_DONE==='")
        
        # 监控输出直到完成
        while True:
            output = self.tmux.capture_output()
            if "===SCRIPT_DONE===" in output:
                return {"success": True, "output": output}
            time.sleep(0.5)
```

## 使用场景

### 1. CI/CD 流程自动化

```python
# 在隔离环境中运行测试
executor = DaytonaTmuxExecutor()
executor.setup_environment("test-env")

# 运行测试脚本
result = executor.execute_script_with_monitoring("/workspace/run-tests.sh")
if result["success"]:
    print("测试通过")
else:
    print(f"测试失败: {result['error']}")
```

### 2. 多服务并行开发

```python
# 启动多个服务
services = {
    "frontend": "npm run dev",
    "backend": "python app.py",
    "database": "docker-compose up postgres"
}

for service_name, command in services.items():
    session = TmuxSession(f"dev-{service_name}")
    session.create_session()
    session.send_command(f"cd /workspace && {command}")
```

### 3. 长时间任务监控

```python
# 执行构建任务
executor.execute_in_daytona("npm run build", use_tmux=True)

# 定期检查进度
while True:
    output = executor.tmux.capture_output(-20)
    if "Build complete" in output:
        break
    
    # 提取进度信息
    progress = extract_progress(output)
    print(f"构建进度: {progress}%")
    time.sleep(5)
```

### 4. 交互式调试

```python
# 创建调试会话
debug_session = TmuxSession("debug-session")
debug_session.create_session()

# 启动调试器
debug_session.send_command("cd /workspace/src")
debug_session.send_command("python -m pdb main.py")

# 附加到会话进行交互
debug_session.attach_session()  # 进入交互模式
```

## 最佳实践

### 1. 资源管理

```python
class ManagedExecutor:
    def __enter__(self):
        self.executor = DaytonaTmuxExecutor()
        return self.executor
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.executor.cleanup()

# 使用上下文管理器确保清理
with ManagedExecutor() as executor:
    executor.setup_environment("temp-workspace")
    executor.execute_script("/workspace/script.sh")
```

### 2. 错误处理

```python
def safe_execute(executor, script_path, max_retries=3):
    """带重试机制的安全执行"""
    for attempt in range(max_retries):
        try:
            result = executor.execute_script_with_monitoring(script_path)
            if result["success"]:
                return result
        except Exception as e:
            print(f"尝试 {attempt + 1} 失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    
    raise Exception("执行失败，已达最大重试次数")
```

### 3. 日志记录

```python
import logging

class LoggingExecutor(DaytonaTmuxExecutor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
    
    def execute_script(self, script_path: str, **kwargs):
        self.logger.info(f"执行脚本: {script_path}")
        result = super().execute_script_with_monitoring(script_path, **kwargs)
        
        if result["success"]:
            self.logger.info(f"脚本执行成功: {script_path}")
        else:
            self.logger.error(f"脚本执行失败: {result['error']}")
        
        return result
```

### 4. 并发控制

```python
from concurrent.futures import ThreadPoolExecutor
import threading

class ConcurrentExecutor:
    def __init__(self, max_workers=5):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()
    
    def execute_parallel_tasks(self, tasks):
        """并行执行多个任务"""
        futures = []
        
        for task in tasks:
            future = self.executor.submit(
                self._execute_task, 
                task['workspace'], 
                task['script']
            )
            futures.append(future)
        
        # 等待所有任务完成
        results = []
        for future in futures:
            results.append(future.result())
        
        return results
```

## 配置建议

### 1. tmux 配置优化

```bash
# ~/.tmux.conf
# 增加历史缓冲区大小
set-option -g history-limit 50000

# 设置窗格同步
bind-key s set-window-option synchronize-panes

# 快速切换会话
bind-key j choose-session
```

### 2. Daytona 配置

```yaml
# daytona.yaml
workspaces:
  default_resources:
    cpu: 2
    memory: 4Gi
    disk: 20Gi
  
  auto_stop:
    enabled: true
    idle_timeout: 30m
```

### 3. Python 环境配置

```python
# config.py
DAYTONA_CONFIG = {
    "default_workspace_timeout": 3600,  # 1小时
    "ssh_timeout": 30,
    "command_retry_count": 3
}

TMUX_CONFIG = {
    "capture_buffer_size": 10000,
    "default_session_prefix": "daytona",
    "command_delay": 0.1  # 命令间延迟
}
```

## 故障排除

### 1. tmux 会话未找到

```python
def ensure_session_exists(session_name):
    """确保会话存在"""
    if not tmux_session_exists(session_name):
        create_tmux_session(session_name)
        time.sleep(0.5)  # 等待会话创建
```

### 2. Daytona 工作区启动失败

```python
def wait_for_workspace_ready(workspace_name, timeout=300):
    """等待工作区就绪"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status = get_workspace_status(workspace_name)
        if status == "running":
            return True
        elif status == "error":
            raise Exception("工作区启动失败")
        
        time.sleep(5)
    
    raise TimeoutError("工作区启动超时")
```

### 3. 输出捕获不完整

```python
def capture_complete_output(session_name, marker="===DONE==="):
    """确保捕获完整输出"""
    output_parts = []
    last_size = 0
    
    while True:
        current_output = capture_tmux_output(session_name)
        
        # 检查是否有新内容
        if len(current_output) > last_size:
            new_content = current_output[last_size:]
            output_parts.append(new_content)
            last_size = len(current_output)
        
        # 检查完成标记
        if marker in current_output:
            break
        
        time.sleep(0.5)
    
    return "".join(output_parts)
```

## 性能优化

### 1. 批量操作

```python
def batch_execute_commands(commands, workspace_name):
    """批量执行命令，减少 SSH 连接开销"""
    script_content = "\n".join(commands)
    
    # 创建临时脚本
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh') as f:
        f.write(script_content)
        f.flush()
        
        # 一次性执行
        return execute_remote_script(workspace_name, f.name)
```

### 2. 连接池

```python
class DaytonaConnectionPool:
    """Daytona SSH 连接池"""
    
    def __init__(self, max_connections=10):
        self.pool = Queue(maxsize=max_connections)
        self.lock = threading.Lock()
    
    def get_connection(self, workspace_name):
        """获取或创建连接"""
        # 实现连接池逻辑
        pass
```

### 3. 异步执行

```python
import asyncio

async def async_execute_script(workspace_name, script_path):
    """异步执行脚本"""
    proc = await asyncio.create_subprocess_exec(
        'daytona', 'ssh', workspace_name, '--', f'bash {script_path}',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await proc.communicate()
    return stdout.decode(), stderr.decode()
```

## 安全考虑

### 1. 命令注入防护

```python
import shlex

def safe_command_execution(command):
    """安全的命令执行"""
    # 使用 shlex 进行安全的参数引用
    safe_command = shlex.quote(command)
    return f"bash -c {safe_command}"
```

### 2. 会话隔离

```python
def create_isolated_session(user_id, task_id):
    """创建隔离的会话"""
    session_name = f"user_{user_id}_task_{task_id}_{uuid.uuid4().hex[:8]}"
    
    # 设置会话权限和限制
    create_tmux_session_with_limits(session_name, {
        "memory_limit": "2G",
        "cpu_limit": "1.0",
        "timeout": 3600
    })
    
    return session_name
```

### 3. 敏感信息处理

```python
def execute_with_secrets(script_path, secrets):
    """安全地传递敏感信息"""
    # 通过环境变量传递，避免命令行泄露
    env_vars = {f"SECRET_{k}": v for k, v in secrets.items()}
    
    with temp_env_vars(env_vars):
        return execute_script(script_path)
```

## 总结

Daytona 和 tmux 的集成提供了强大的远程开发环境管理能力：

1. **环境隔离**：每个任务在独立的工作区和会话中运行
2. **并行执行**：支持同时管理多个任务和服务
3. **实时监控**：通过 tmux capture-pane 实现输出监控
4. **灵活控制**：支持启动、停止、重启等完整的生命周期管理
5. **可扩展性**：易于集成到现有的 CI/CD 流程中

这种集成方案特别适合：
- 自动化测试和构建
- 多服务应用开发
- 远程调试和故障排查
- 团队协作开发环境管理