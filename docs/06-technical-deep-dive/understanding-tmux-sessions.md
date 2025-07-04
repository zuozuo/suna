# 理解 SandboxShellTool 中的会话管理

## 什么是 tmux 会话？

在 SandboxShellTool 中，**会话（Session）** 指的是 **tmux 会话**。tmux (Terminal Multiplexer) 是一个终端复用器，它可以让你在一个终端窗口中创建、访问和控制多个独立的终端会话。

### tmux 会话的核心概念

1. **独立的终端环境**
   - 每个 tmux 会话就像一个独立的虚拟终端
   - 有自己的进程空间和环境
   - 可以在后台持续运行

2. **持久性**
   - 即使你断开连接，会话仍在后台运行
   - 可以随时重新连接到会话
   - 进程不会因为连接断开而终止

3. **命名管理**
   - 每个会话可以有唯一的名称
   - 通过名称可以管理和访问特定会话

## 在 SandboxShellTool 中的应用

### 1. 创建会话

```bash
# 当你执行命令时，工具会创建一个 tmux 会话
tmux new-session -d -s dev_server
# -d: 在后台创建（detached）
# -s: 指定会话名称
```

在代码中体现为：
```python
# 检查会话是否存在
check_session = await self._execute_raw_command(
    f"tmux has-session -t {session_name} 2>/dev/null || echo 'not_exists'"
)

# 如果不存在，创建新会话
if not session_exists:
    await self._execute_raw_command(f"tmux new-session -d -s {session_name}")
```

### 2. 在会话中执行命令

```bash
# 向会话发送命令
tmux send-keys -t dev_server "npm run dev" Enter
# -t: 目标会话
# 命令会在该会话中执行
```

代码实现：
```python
# 构建完整命令（包含目录切换）
full_command = f"cd {cwd} && {command}"

# 发送到 tmux 会话
await self._execute_raw_command(
    f'tmux send-keys -t {session_name} "{wrapped_command}" Enter'
)
```

### 3. 会话的好处

#### 状态保持
```xml
<!-- 第一次：启动服务器 -->
<execute-command session_name="my_server">
cd /workspace/app
npm start
</execute-command>

<!-- 稍后：在同一会话中执行其他命令 -->
<execute-command session_name="my_server">
# 不需要再次 cd，因为会话保持了之前的状态
npm run test
</execute-command>
```

#### 并行任务
```xml
<!-- 同时运行多个独立任务 -->
<execute-command session_name="frontend">
npm run dev
</execute-command>

<execute-command session_name="backend">
python app.py
</execute-command>

<execute-command session_name="database">
docker run postgres
</execute-command>
```

### 4. 实际开发场景

想象你在开发一个全栈应用：

```xml
<!-- 1. 启动后端 API 服务器 -->
<execute-command session_name="backend_api">
cd backend && npm run dev
</execute-command>
<!-- 这个服务器会一直运行在 "backend_api" 会话中 -->

<!-- 2. 启动前端开发服务器 -->
<execute-command session_name="frontend_dev">
cd frontend && npm run dev
</execute-command>
<!-- 前端服务器在另一个独立的 "frontend_dev" 会话中运行 -->

<!-- 3. 随时检查后端日志 -->
<check-command-output session_name="backend_api" />
<!-- 可以看到后端服务器的所有输出 -->

<!-- 4. 需要重启后端时 -->
<terminate-command session_name="backend_api" />
<!-- 然后重新启动 -->
```

## 会话 vs 普通命令执行

### 没有会话管理（传统方式）
- 命令执行完就结束
- 无法保持状态
- 长时间任务会阻塞
- 无法并行执行多个任务

### 有会话管理（tmux 方式）
- 命令在独立会话中运行
- 可以随时查看输出
- 支持多个并行任务
- 保持工作目录和环境变量
- 进程在后台持续运行

## 形象比喻

可以把 tmux 会话想象成：

### 1. 多个独立的终端窗口
- 每个会话就像打开了一个新的终端窗口
- 可以在不同窗口运行不同任务
- 窗口之间相互独立

### 2. 后台运行的程序
- 就像最小化的程序仍在运行
- 随时可以"切换"回去查看
- 不会因为关闭主窗口而停止

### 3. 工作空间
- 每个会话是一个独立的工作空间
- 有自己的当前目录、环境变量等
- 状态在会话生命周期内保持

## 会话生命周期管理

### 创建
```xml
<execute-command session_name="my_task">
echo "Starting task..."
</execute-command>
```

### 监控
```xml
<!-- 查看输出但不终止 -->
<check-command-output session_name="my_task" />

<!-- 列出所有活跃会话 -->
<list-commands />
```

### 终止
```xml
<!-- 查看最终输出并终止 -->
<check-command-output session_name="my_task" kill_session="true" />

<!-- 或直接终止 -->
<terminate-command session_name="my_task" />
```

## 最佳实践

### 1. 使用描述性的会话名
```xml
<!-- 好的命名 -->
<execute-command session_name="prod_api_server">
<execute-command session_name="test_runner">
<execute-command session_name="db_migration">

<!-- 避免模糊的名称 -->
<execute-command session_name="session1">
<execute-command session_name="temp">
```

### 2. 及时清理会话
```xml
<!-- 完成任务后清理 -->
<check-command-output session_name="build_process" kill_session="true" />
```

### 3. 合理使用阻塞模式
```xml
<!-- 短时间任务使用阻塞模式 -->
<execute-command blocking="true">
npm install
</execute-command>

<!-- 长时间任务使用会话 -->
<execute-command session_name="dev_server">
npm run dev
</execute-command>
```

## 技术细节

### tmux 命令参考
| 命令 | 作用 |
|------|------|
| `tmux new-session -d -s name` | 创建后台会话 |
| `tmux send-keys -t name "cmd" Enter` | 发送命令到会话 |
| `tmux capture-pane -t name -p` | 捕获会话输出 |
| `tmux kill-session -t name` | 终止会话 |
| `tmux list-sessions` | 列出所有会话 |
| `tmux has-session -t name` | 检查会话是否存在 |

### tmux capture-pane 详解

`tmux capture-pane` 是 tmux 中用于捕获窗格（pane）内容的核心命令，在 SandboxShellTool 中用于获取命令执行的输出。

#### 基本语法
```bash
tmux capture-pane [-t target-pane] [-p] [-S start-line] [-E end-line] [-e] [-J]
```

#### 主要选项说明
| 选项 | 作用 | 示例 |
|------|------|------|
| `-t target` | 指定目标窗格 | `-t session_name` |
| `-p` | 输出到标准输出而不是缓冲区 | 常用于直接获取内容 |
| `-S start` | 指定开始行（-表示历史开始） | `-S -` 或 `-S -100` |
| `-E end` | 指定结束行（-表示历史结束） | `-E -` |
| `-e` | 包含转义序列（保留颜色等格式） | 保留原始格式 |
| `-J` | 连接折行的文本 | 处理长行文本 |
| `-b buffer` | 保存到指定缓冲区 | `-b capture-buffer` |

#### 常见使用场景

1. **捕获当前可见内容**
```bash
tmux capture-pane -t my_session -p
```

2. **捕获完整历史记录**
```bash
tmux capture-pane -t my_session -S - -E - -p
```

3. **捕获最近100行**
```bash
tmux capture-pane -t my_session -S -100 -p
```

4. **保留格式信息**
```bash
tmux capture-pane -t my_session -e -p
```

5. **处理长行文本**
```bash
tmux capture-pane -t my_session -J -p
```

#### 在 SandboxShellTool 中的应用

```python
# 捕获会话输出
output = await self._execute_raw_command(
    f"tmux capture-pane -t {session_name} -p"
)

# 捕获包含历史的输出
full_output = await self._execute_raw_command(
    f"tmux capture-pane -t {session_name} -S - -p"
)
```

#### 实际示例

```bash
# 创建会话并执行命令
tmux new-session -d -s build_session
tmux send-keys -t build_session "npm run build" Enter

# 等待一段时间后捕获输出
sleep 5
tmux capture-pane -t build_session -p

# 捕获完整构建日志
tmux capture-pane -t build_session -S - -E - -p > build.log

# 清理会话
tmux kill-session -t build_session
```

#### 注意事项

1. **缓冲区限制**：tmux 有历史缓冲区大小限制，超出部分会被丢弃
2. **性能考虑**：捕获大量历史记录可能影响性能
3. **格式处理**：使用 `-e` 选项时需要处理 ANSI 转义序列
4. **时机问题**：命令执行后需要适当延迟才能捕获完整输出

### 会话隔离
- 每个会话有独立的：
  - 进程树
  - 工作目录
  - 环境变量
  - 输入/输出缓冲区
- 会话间完全隔离，互不影响

## 总结

tmux 会话管理是 SandboxShellTool 的核心特性，它让 AI 助手能够：

1. **并行处理多个任务** - 同时运行前端、后端、数据库等
2. **保持任务状态** - 工作目录、环境变量等在会话中保持
3. **监控长时间任务** - 随时查看服务器日志、构建进度等
4. **灵活的任务控制** - 启动、监控、终止任务

这种设计让 AI 助手能够像真实开发者一样，同时管理多个任务，提供了强大而灵活的命令执行能力。