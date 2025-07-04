# Suna 工具快速参考

## 🚀 常用工具速查

### 文件操作
```xml
<!-- 读取文件 -->
<read>
    <path>/path/to/file.txt</path>
</read>

<!-- 写入文件 -->
<write>
    <path>/path/to/file.txt</path>
    <content>文件内容</content>
</write>

<!-- 创建目录 -->
<create_directory>
    <path>/path/to/directory</path>
</create_directory>

<!-- 列出目录内容 -->
<list_directory>
    <path>/path/to/directory</path>
</list_directory>
```

### 命令执行
```xml
<!-- 执行单个命令 -->
<execute>
    <command>ls -la</command>
    <stream>true</stream>
</execute>

<!-- 在 tmux 会话中执行 -->
<execute_in_session>
    <session_name>dev_server</session_name>
    <command>npm run dev</command>
</execute_in_session>

<!-- 终止命令 -->
<terminate>
    <session_name>dev_server</session_name>
</terminate>
```

### 浏览器自动化
```xml
<!-- 导航到 URL -->
<navigate>
    <url>https://example.com</url>
</navigate>

<!-- 点击元素 -->
<click>
    <selector>#submit-button</selector>
</click>

<!-- 输入文本 -->
<type>
    <selector>#username</selector>
    <text>myusername</text>
</type>

<!-- 截屏 -->
<screenshot>
    <format>base64</format>
</screenshot>
```

### 网络搜索
```xml
<!-- 搜索网页 -->
<web_search>
    <query>Suna AI assistant tutorial</query>
    <max_results>10</max_results>
</web_search>

<!-- 爬取网页内容 -->
<web_crawl>
    <url>https://example.com/article</url>
    <extract>main_content</extract>
</web_crawl>
```

### 消息与展示
```xml
<!-- 发送消息给用户 -->
<message>
    <content>任务完成！</content>
    <type>success</type>
</message>

<!-- 展示扩展内容 -->
<expand_message>
    <content>这是一段很长的内容...</content>
    <format>markdown</format>
</expand_message>
```

## 📋 工具参数说明

### SandboxShellTool
| 方法 | 参数 | 说明 |
|------|------|------|
| execute | command, stream, session_name | 执行命令 |
| execute_in_session | session_name, command | 在会话中执行 |
| list_sessions | - | 列出所有会话 |
| terminate | session_name | 终止会话 |

### SandboxFilesTool
| 方法 | 参数 | 说明 |
|------|------|------|
| read | path | 读取文件 |
| write | path, content | 写入文件 |
| create_directory | path | 创建目录 |
| list_directory | path | 列出目录 |
| delete | path | 删除文件/目录 |

### SandboxBrowserTool
| 方法 | 参数 | 说明 |
|------|------|------|
| navigate | url | 导航到URL |
| screenshot | format | 截屏(base64/url) |
| click | selector | 点击元素 |
| type | selector, text | 输入文本 |
| select | selector, value | 选择下拉项 |
| wait | selector, timeout | 等待元素 |

### SandboxWebSearchTool
| 方法 | 参数 | 说明 |
|------|------|------|
| web_search | query, max_results | 搜索网页 |
| web_crawl | url, extract | 爬取内容 |

## 🎯 使用示例

### 创建并运行 Node.js 项目
```xml
<!-- 1. 创建项目目录 -->
<create_directory>
    <path>/home/user/my-app</path>
</create_directory>

<!-- 2. 创建 package.json -->
<write>
    <path>/home/user/my-app/package.json</path>
    <content>{
  "name": "my-app",
  "version": "1.0.0",
  "scripts": {
    "start": "node index.js"
  }
}</content>
</write>

<!-- 3. 创建主文件 -->
<write>
    <path>/home/user/my-app/index.js</path>
    <content>console.log('Hello, Suna!');</content>
</write>

<!-- 4. 运行项目 -->
<execute>
    <command>cd /home/user/my-app && npm start</command>
</execute>
```

### 网页数据采集
```xml
<!-- 1. 搜索相关网页 -->
<web_search>
    <query>AI assistant comparison 2024</query>
    <max_results>5</max_results>
</web_search>

<!-- 2. 访问搜索结果 -->
<navigate>
    <url>https://example.com/ai-comparison</url>
</navigate>

<!-- 3. 截屏保存 -->
<screenshot>
    <format>base64</format>
</screenshot>

<!-- 4. 提取内容 -->
<web_crawl>
    <url>https://example.com/ai-comparison</url>
    <extract>main_content</extract>
</web_crawl>
```

## ⚡ 性能建议

1. **批量操作**
   - 使用单个 `write` 而不是多次小写入
   - 批量创建目录结构

2. **流式处理**
   - 对长时间运行的命令使用 `stream: true`
   - 大文件操作考虑分块处理

3. **会话管理**
   - 复用 tmux 会话避免重复创建
   - 及时清理不用的会话

## 🔒 安全提醒

1. **路径验证**
   - 工具会自动验证路径安全性
   - 不能访问沙箱外的文件

2. **命令注入**
   - 避免直接拼接用户输入到命令
   - 使用参数化的方式传递

3. **资源限制**
   - 长时间运行的操作会被自动终止
   - 文件大小有上限限制

## 🆘 常见问题

**Q: 为什么文件操作失败？**
A: 检查路径是否在沙箱内，是否有权限

**Q: 命令执行超时怎么办？**
A: 使用 tmux 会话执行长时间任务

**Q: 浏览器操作不稳定？**
A: 添加适当的等待时间，使用更具体的选择器

**Q: 如何处理大文件？**
A: 使用流式读取，或分块处理