# Suna Sandbox 工具详细分析

本文档详细分析了 Suna 项目中每个 Sandbox 工具的具体实现，包括参数定义、执行方法、与 sandbox API 的交互方式以及错误处理机制。

## 目录

1. [工具基类架构](#工具基类架构)
2. [SandboxShellTool - 命令执行工具](#sandboxshelltool---命令执行工具)
3. [SandboxFilesTool - 文件操作工具](#sandboxfilestool---文件操作工具)
4. [SandboxBrowserTool - 浏览器自动化工具](#sandboxbrowsertool---浏览器自动化工具)
5. [SandboxVisionTool - 图像处理工具](#sandboxvisiontool---图像处理工具)
6. [SandboxExposeTool - 端口暴露工具](#sandboxexposetool---端口暴露工具)
7. [SandboxDeployTool - 部署工具](#sandboxdeploytool---部署工具)

## 工具基类架构

### SandboxToolsBase

所有 Sandbox 工具都继承自 `SandboxToolsBase` 基类，该类提供了统一的 sandbox 访问机制。

```python
class SandboxToolsBase(Tool):
    """Base class for all sandbox tools that provides project-based sandbox access."""
    
    def __init__(self, project_id: str, thread_manager: Optional[ThreadManager] = None):
        super().__init__()
        self.project_id = project_id
        self.thread_manager = thread_manager
        self.workspace_path = "/workspace"
        self._sandbox = None
        self._sandbox_id = None
        self._sandbox_pass = None
```

**核心方法：**

1. **`_ensure_sandbox()`** - 确保 sandbox 实例可用
   - 从数据库获取项目信息
   - 提取 sandbox ID 和密码
   - 调用 `get_or_start_sandbox()` 获取或启动 sandbox

2. **`clean_path()`** - 路径规范化
   - 确保所有路径相对于 `/workspace` 目录
   - 防止路径遍历攻击

## SandboxShellTool - 命令执行工具

### 功能概述
提供在 sandbox 环境中执行 shell 命令的能力，支持同步和异步执行模式。

### 核心特性

1. **Tmux 会话管理**
   - 使用 tmux 管理长时间运行的进程
   - 支持命名会话，便于追踪和管理
   - 会话状态持久化

2. **执行模式**
   - **非阻塞模式（默认）**：立即返回，适合启动服务器等长时间运行的任务
   - **阻塞模式**：等待命令完成并返回输出

### 主要方法

#### 1. `execute_command`

```python
@openapi_schema({
    "parameters": {
        "properties": {
            "command": {"type": "string"},
            "folder": {"type": "string"},
            "session_name": {"type": "string"},
            "blocking": {"type": "boolean", "default": False},
            "timeout": {"type": "integer", "default": 60}
        }
    }
})
async def execute_command(self, command: str, folder: Optional[str] = None, 
                         session_name: Optional[str] = None, 
                         blocking: bool = False, timeout: int = 60) -> ToolResult:
```

**执行流程：**
1. 确保 sandbox 已初始化
2. 构建工作目录路径
3. 检查或创建 tmux 会话
4. 在 tmux 会话中执行命令
5. 根据执行模式返回结果

**关键实现细节：**

```python
# 创建 tmux 会话
await self._execute_raw_command(f"tmux new-session -d -s {session_name}")

# 在会话中执行命令
full_command = f"cd {cwd} && {command}"
wrapped_command = full_command.replace('"', '\\"')
await self._execute_raw_command(f'tmux send-keys -t {session_name} "{wrapped_command}" Enter')
```

#### 2. `check_command_output`

检查之前执行命令的输出：

```python
async def check_command_output(self, session_name: str, kill_session: bool = False) -> ToolResult:
    # 获取 tmux pane 输出
    output_result = await self._execute_raw_command(f"tmux capture-pane -t {session_name} -p -S - -E -")
    
    # 可选择终止会话
    if kill_session:
        await self._execute_raw_command(f"tmux kill-session -t {session_name}")
```

### 错误处理

- 会话创建失败时的异常捕获
- 命令执行超时处理
- 清理机制：出错时自动清理会话

## SandboxFilesTool - 文件操作工具

### 功能概述
提供文件系统操作能力，包括创建、读取、更新和删除文件。

### 主要方法

#### 1. `create_file`

```python
async def create_file(self, file_path: str, file_contents: str, permissions: str = "644") -> ToolResult:
    # 路径清理和验证
    file_path = self.clean_path(file_path)
    full_path = f"{self.workspace_path}/{file_path}"
    
    # 检查文件是否已存在
    if self._file_exists(full_path):
        return self.fail_response(f"File '{file_path}' already exists")
    
    # 创建父目录
    parent_dir = '/'.join(full_path.split('/')[:-1])
    if parent_dir:
        self.sandbox.fs.create_folder(parent_dir, "755")
    
    # 写入文件
    self.sandbox.fs.upload_file(file_contents.encode(), full_path)
    self.sandbox.fs.set_file_permissions(full_path, permissions)
```

**特殊处理：**
- 自动检测 `index.html` 文件并提供预览链接
- 自动创建父目录结构

#### 2. `str_replace`

精确字符串替换功能：

```python
async def str_replace(self, file_path: str, old_str: str, new_str: str) -> ToolResult:
    # 读取文件内容
    content = self.sandbox.fs.download_file(full_path).decode()
    
    # 验证唯一性
    occurrences = content.count(old_str)
    if occurrences == 0:
        return self.fail_response(f"String '{old_str}' not found")
    if occurrences > 1:
        lines = [i+1 for i, line in enumerate(content.split('\n')) if old_str in line]
        return self.fail_response(f"Multiple occurrences found in lines {lines}")
    
    # 执行替换
    new_content = content.replace(old_str, new_str)
    self.sandbox.fs.upload_file(new_content.encode(), full_path)
```

### 文件排除机制

使用 `should_exclude_file()` 函数排除：
- 系统文件（`.git`, `.DS_Store` 等）
- 依赖目录（`node_modules`, `venv` 等）
- 二进制文件

## SandboxBrowserTool - 浏览器自动化工具

### 功能概述
提供浏览器自动化能力，支持页面导航、元素交互、截图等功能。

### 架构设计

通过 HTTP API 与浏览器自动化服务通信：

```python
async def _execute_browser_action(self, endpoint: str, params: dict = None, method: str = "POST") -> ToolResult:
    # 构建 API URL
    url = f"http://localhost:8003/api/automation/{endpoint}"
    
    # 使用 curl 执行请求
    curl_cmd = f"curl -s -X {method} '{url}' -H 'Content-Type: application/json'"
    if params:
        json_data = json.dumps(params)
        curl_cmd += f" -d '{json_data}'"
    
    response = self.sandbox.process.exec(curl_cmd, timeout=30)
```

### 主要功能

#### 1. 页面导航

```python
async def browser_navigate_to(self, url: str) -> ToolResult:
    return await self._execute_browser_action("navigate_to", {"url": url})
```

#### 2. 元素交互

```python
async def browser_click_element(self, index: int) -> ToolResult:
    return await self._execute_browser_action("click_element", {"index": index})

async def browser_input_text(self, index: int, text: str) -> ToolResult:
    return await self._execute_browser_action("input_text", {"index": index, "text": text})
```

#### 3. 截图处理

**Base64 图像验证流程：**

```python
def _validate_base64_image(self, base64_string: str, max_size_mb: int = 10) -> tuple[bool, str]:
    # 1. 基础验证
    if not base64_string or len(base64_string) < 10:
        return False, "Base64 string is empty or too short"
    
    # 2. 格式验证
    if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', base64_string):
        return False, "Invalid base64 characters detected"
    
    # 3. 解码验证
    image_data = base64.b64decode(base64_string, validate=True)
    
    # 4. PIL 图像验证
    with Image.open(io.BytesIO(image_data)) as img:
        img.verify()
        if img.format not in {'JPEG', 'PNG', 'GIF', 'BMP', 'WEBP', 'TIFF'}:
            return False, f"Unsupported image format: {img.format}"
```

**截图上传流程：**

```python
if "screenshot_base64" in result:
    is_valid, validation_message = self._validate_base64_image(screenshot_data)
    if is_valid:
        image_url = await upload_base64_image(screenshot_data)
        result["image_url"] = image_url
```

### 消息管理

将浏览器状态作为特殊消息类型存储：

```python
added_message = await self.thread_manager.add_message(
    thread_id=self.thread_id,
    type="browser_state",
    content=result,
    is_llm_message=False
)
```

## SandboxVisionTool - 图像处理工具

### 功能概述
允许 AI Agent "看到"图像文件，支持本地文件和 URL。

### 核心特性

1. **图像压缩**
   - 自动调整大小（最大 1920x1080）
   - 智能格式转换
   - 保持合理质量（JPEG 85%，PNG 6级压缩）

2. **多源支持**
   - 本地文件系统
   - HTTP/HTTPS URL

### 压缩算法

```python
def compress_image(self, image_bytes: bytes, mime_type: str, file_path: str) -> Tuple[bytes, str]:
    img = Image.open(BytesIO(image_bytes))
    
    # RGBA 到 RGB 转换
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    
    # 尺寸调整
    if width > DEFAULT_MAX_WIDTH or height > DEFAULT_MAX_HEIGHT:
        ratio = min(DEFAULT_MAX_WIDTH / width, DEFAULT_MAX_HEIGHT / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
```

### 图像上下文管理

```python
# 创建图像上下文消息
image_context_data = {
    "mime_type": compressed_mime_type,
    "base64": base64_image,
    "file_path": cleaned_path,
    "original_size": original_size,
    "compressed_size": len(compressed_bytes)
}

await self.thread_manager.add_message(
    thread_id=self.thread_id,
    type="image_context",
    content=image_context_data,
    is_llm_message=False
)
```

## SandboxExposeTool - 端口暴露工具

### 功能概述
将 sandbox 内部端口暴露到公网，使服务可被外部访问。

### 核心功能

#### 1. 服务就绪检查

```python
async def _wait_for_sandbox_services(self, timeout: int = 30) -> bool:
    while time.time() - start_time < timeout:
        # 检查 supervisord 状态
        result = self.sandbox.process.exec("supervisorctl status", timeout=10)
        
        if result.exit_code == 0:
            status_output = result.output
            if "http_server" in status_output and "RUNNING" in status_output:
                return True
        
        await asyncio.sleep(2)
```

#### 2. 端口验证

```python
# 检查端口是否有服务监听
if port not in [6080, 8080, 8003]:  # 跳过已知系统端口
    port_check = self.sandbox.process.exec(f"netstat -tlnp | grep :{port}", timeout=5)
    if port_check.exit_code != 0:
        return self.fail_response(f"No service is currently listening on port {port}")
```

#### 3. 获取预览链接

```python
# 获取公开访问 URL
preview_link = self.sandbox.get_preview_link(port)
url = preview_link.url if hasattr(preview_link, 'url') else str(preview_link)
```

## SandboxDeployTool - 部署工具

### 功能概述
将静态网站从 sandbox 部署到 Cloudflare Pages。

### 部署流程

1. **目录验证**
   ```python
   dir_info = self.sandbox.fs.get_file_info(full_path)
   if not dir_info.is_dir:
       return self.fail_response(f"'{directory_path}' is not a directory")
   ```

2. **Cloudflare 部署**
   ```python
   project_name = f"{self.sandbox_id}-{name}"
   deploy_cmd = f'''
       cd {self.workspace_path} && 
       export CLOUDFLARE_API_TOKEN={self.cloudflare_api_token} && 
       (npx wrangler pages deploy {full_path} --project-name {project_name} || 
       (npx wrangler pages project create {project_name} --production-branch production && 
       npx wrangler pages deploy {full_path} --project-name {project_name}))
   '''
   ```

### 错误处理

- API Token 验证
- 目录存在性检查
- 部署命令执行状态检查

## 与 Sandbox API 的交互

### Daytona SDK 集成

所有工具通过 Daytona SDK 与 sandbox 交互：

```python
# 初始化配置
daytona_config = DaytonaConfig(
    api_key=config.DAYTONA_API_KEY,
    server_url=config.DAYTONA_SERVER_URL,
    target=config.DAYTONA_TARGET
)

# 创建客户端
daytona = Daytona(daytona_config)
```

### Sandbox 生命周期管理

```python
async def get_or_start_sandbox(sandbox_id: str):
    sandbox = daytona.get(sandbox_id)
    
    # 检查状态并启动
    if sandbox.state in [SandboxState.ARCHIVED, SandboxState.STOPPED]:
        daytona.start(sandbox)
        start_supervisord_session(sandbox)
    
    return sandbox
```

### 核心 API 接口

1. **文件系统操作**
   - `sandbox.fs.upload_file()` - 上传文件
   - `sandbox.fs.download_file()` - 下载文件
   - `sandbox.fs.create_folder()` - 创建目录
   - `sandbox.fs.delete_file()` - 删除文件

2. **进程管理**
   - `sandbox.process.exec()` - 执行命令
   - `sandbox.process.create_session()` - 创建会话
   - `sandbox.process.execute_session_command()` - 在会话中执行

3. **网络功能**
   - `sandbox.get_preview_link()` - 获取预览链接

## 错误处理机制

### 统一错误响应

所有工具使用继承自基类的错误处理方法：

```python
def success_response(self, data):
    return ToolResult(success=True, data=data)

def fail_response(self, message):
    return ToolResult(success=False, data={"error": message})
```

### 错误处理策略

1. **预验证**
   - 参数验证（路径、端口范围等）
   - 权限检查
   - 资源可用性检查

2. **异常捕获**
   - 网络异常
   - 文件系统异常
   - API 调用异常

3. **清理机制**
   - tmux 会话清理
   - 临时资源释放
   - 状态重置

## 性能优化

1. **连接复用**
   - 单例 sandbox 实例
   - 持久化会话管理

2. **异步操作**
   - 所有工具方法都是异步的
   - 支持并发操作

3. **资源限制**
   - 图像大小限制（10MB 原始，5MB 压缩）
   - 命令执行超时
   - 内存使用控制

## 安全考虑

1. **路径安全**
   - 所有路径都经过 `clean_path()` 处理
   - 防止目录遍历攻击

2. **命令注入防护**
   - 命令参数转义
   - 使用参数化 API 调用

3. **权限隔离**
   - 文件权限管理
   - 进程隔离（tmux 会话）

4. **敏感信息保护**
   - API Token 不在日志中暴露
   - Base64 数据验证防止恶意输入

## 总结

Suna 的 Sandbox 工具集提供了完整的开发环境操作能力：

- **SandboxShellTool**：强大的命令执行和进程管理
- **SandboxFilesTool**：完整的文件系统操作
- **SandboxBrowserTool**：丰富的浏览器自动化功能
- **SandboxVisionTool**：智能的图像处理和压缩
- **SandboxExposeTool**：便捷的服务暴露机制
- **SandboxDeployTool**：一键部署到生产环境

这些工具通过统一的基类架构、标准的错误处理和安全机制，为 AI Agent 提供了安全、高效、可靠的开发环境操作能力。