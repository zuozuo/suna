# 第 1 周快速开始指南

## 环境检查清单

在开始之前，确保您的系统满足以下要求：

```bash
# 检查 Python 版本（需要 3.11+）
python --version

# 检查 Node.js 版本（需要 18+）
node --version

# 检查 Docker（可选但推荐）
docker --version

# 检查 Git
git --version
```

## 步骤 1：项目设置

### 1.1 克隆并设置项目

```bash
# 克隆项目
git clone https://github.com/kortix-ai/suna.git
cd suna

# 创建 Python 虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 运行设置向导
python setup.py
```

### 1.2 设置向导注意事项

设置向导会引导您完成 14 个步骤：

1. **Supabase 设置**
   - 如果没有账户，访问 https://supabase.com 创建
   - 创建新项目时，保存好数据库密码

2. **API 密钥配置**
   - 至少需要一个 LLM 提供商（推荐 Anthropic 或 OpenAI）
   - Tavily API 用于网页搜索（可选但推荐）

3. **本地开发设置**
   - Redis：使用 Docker 最简单
   - Daytona：Agent 执行环境（可选）

## 步骤 2：验证安装

### 2.1 启动服务

```bash
# 启动所有服务
python start.py

# 或分别启动
cd backend
uvicorn api:app --reload --port 8000

# 新终端
cd frontend
npm install
npm run dev
```

### 2.2 创建测试用户

```bash
cd backend
python create_test_user.py test@example.com testpass123
```

### 2.3 访问应用

- 前端：http://localhost:3000
- 后端 API：http://localhost:8000/docs

## 步骤 3：第一次探索

### 3.1 功能体验清单

- [ ] 登录系统
- [ ] 创建第一个对话
- [ ] 尝试简单的问答
- [ ] 测试网页搜索功能
- [ ] 查看文件管理功能
- [ ] 探索设置页面

### 3.2 尝试示例提示词

1. **基础对话**
   ```
   你好，请介绍一下你自己和你能做什么？
   ```

2. **网页搜索**
   ```
   搜索最新的 AI 发展趋势并总结
   ```

3. **文件操作**
   ```
   创建一个名为 test.txt 的文件，内容是"Hello Suna"
   ```

## 故障排除

### 常见问题

1. **Supabase 连接错误**
   - 检查 .env 文件中的 URL 和密钥
   - 确保 Supabase 项目正在运行

2. **LLM API 错误**
   - 验证 API 密钥正确
   - 检查是否有余额/配额

3. **前端构建错误**
   ```bash
   # 清理并重新安装
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   ```

## 学习任务

### 任务 1：理解项目结构

创建一个 `project-structure.md` 文件，记录您对以下内容的理解：

1. 前后端如何通信？
2. 用户认证流程是怎样的？
3. Agent 如何执行工具调用？

### 任务 2：修改欢迎消息

1. 找到前端显示欢迎消息的组件
2. 修改默认的欢迎文本
3. 添加您的个人风格

### 任务 3：添加日志

在后端添加一些调试日志：

```python
# 在 backend/api.py 中
from utils.logger import logger

# 在某个端点中添加
logger.info(f"用户 {user_id} 正在访问端点")
```

## 本周目标检查

- [ ] 成功运行完整的开发环境
- [ ] 创建并登录测试用户
- [ ] 完成所有示例功能测试
- [ ] 理解基本的项目结构
- [ ] 完成至少一个代码修改

## 下周预告

下周我们将深入学习：
- FastAPI 路由和中间件
- Supabase 实时订阅
- React Query 数据获取
- 创建您的第一个 API 端点

记得保存您的学习笔记和遇到的问题！