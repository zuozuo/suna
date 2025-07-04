# Suna 项目文档总览

欢迎来到 Suna 项目文档！Suna 是一个开源的通用 AI Agent 平台，提供了强大的工具系统、灵活的工作流引擎和完善的开发框架。

## 📚 文档导航

### 🚀 [01. 入门指南](./01-getting-started/)
适合初次接触 Suna 的开发者，快速了解项目并开始使用。

- [**项目概述**](./01-getting-started/overview.md) - 了解 Suna 是什么，核心特性和应用场景
- [**部署指南**](./01-getting-started/SELF-HOSTING.md) - 详细的自托管部署步骤
- [**第一个示例**](./01-getting-started/hello-execution-flow.md) - 通过 "Hello" 示例理解系统运行流程
- [**系统交互图**](./01-getting-started/sequence-diagram.md) - 可视化的系统组件交互关系

### 🏗️ [02. 核心架构](./02-core-architecture/)
深入理解 Suna 的架构设计和核心组件。

- [**架构总览**](./02-core-architecture/architecture-overview.md) - 系统整体架构和设计理念
- [**聊天流程分析**](./02-core-architecture/chat-flow-analysis.md) - 端到端的对话处理流程
- [**异步任务架构**](./02-core-architecture/async-task-architecture.md) - 基于 Redis 的异步任务系统
- [**Agent 后台执行系统**](./02-core-architecture/agent-background-execution.md) ⭐ - Agent 后台任务执行详解
- [**ThreadManager 核心组件**](./02-core-architecture/thread-manager-analysis.md) - 对话管理的核心引擎
- [**实时通信机制**](./02-core-architecture/suna-sse-implementation.md) - SSE 实时响应实现
- [**任务队列系统**](./02-core-architecture/dramatiq-in-suna.md) - Dramatiq 在 Suna 中的应用

### 🛠️ [03. 工具系统](./03-tool-system/)
了解 Suna 强大的工具系统和扩展能力。

- [**工具系统总览**](./03-tool-system/tool-system-overview.md) - 工具系统设计和使用指南
- [**架构详解**](./03-tool-system/tool-system-architecture.md) - 工具系统的详细架构分析
- [**自定义工具开发**](./03-tool-system/custom-tool-development-guide.md) ⭐ - 创建自定义工具的完整指南
- [**API 示例**](./03-tool-system/tool-calling-api-examples.md) - 工具调用的具体 API 示例
- [**双模态调用**](./03-tool-system/dual-mode-tool-calling.md) - OpenAI 和 Anthropic 格式支持
- [**沙盒工具指南**](./03-tool-system/sandboxshelltool-guide.md) - 安全的代码执行环境
- [**工具快速参考**](./03-tool-system/tools-quick-reference.md) - 所有可用工具的快速查询

### 🔌 [04. 扩展系统](./04-extension-systems/)
探索 Suna 的扩展能力和集成方案。

- [**MCP 集成**](./04-extension-systems/mcp-integration.md) - Model Context Protocol 集成指南
- [**工作流引擎**](./04-extension-systems/workflow-engine.md) - 可视化工作流自动化系统
- [**Ask 工具流程**](./04-extension-systems/ask-tool-backend-flow.md) - Ask 工具的后端实现

### 🎯 [05. 高级功能](./05-advanced-features/)
企业级功能和高级特性。

- [**认证和多租户**](./05-advanced-features/auth-and-multi-tenancy-architecture.md) - 企业级权限管理
- [**商业化计费**](./05-advanced-features/commercialization-core-billing-system.md) - 计费系统设计
- [**分布式系统**](./05-advanced-features/distributed-systems.md) - 分布式架构设计
- [**异步执行流程**](./05-advanced-features/async-task-execution-flow.md) - 详细的异步任务执行分析
- [**系统架构优化方案**](./05-advanced-features/system-architecture-optimization.md) ⭐ - 全面的架构优化指南

### 🔬 [06. 技术深度解析](./06-technical-deep-dive/)
技术细节和实现原理。

- [**任务队列对比**](./06-technical-deep-dive/dramatiq-vs-celery.md) - Dramatiq vs Celery 选型分析
- [**Dramatiq 详解**](./06-technical-deep-dive/dramatiq-actor-broker-explained.md) - Actor 模型和 Broker 机制
- [**分布式锁实现**](./06-technical-deep-dive/distributed-lock-implementation.md) - Redis 分布式锁详解
- [**Tmux 会话管理**](./06-technical-deep-dive/understanding-tmux-sessions.md) - 终端会话管理机制

## 🎓 推荐学习路径

### 新手入门路径
1. 阅读[项目概述](./01-getting-started/overview.md)了解 Suna
2. 按照[部署指南](./01-getting-started/SELF-HOSTING.md)搭建环境
3. 通过[第一个示例](./01-getting-started/hello-execution-flow.md)理解基本流程
4. 学习[架构总览](./02-core-architecture/architecture-overview.md)掌握整体设计

### 开发者进阶路径
1. 深入理解[工具系统](./03-tool-system/tool-system-overview.md)
2. 掌握[ThreadManager](./02-core-architecture/thread-manager-analysis.md)核心组件
3. 学习[MCP 集成](./04-extension-systems/mcp-integration.md)扩展能力
4. 探索[工作流引擎](./04-extension-systems/workflow-engine.md)自动化能力

### 架构师深入路径
1. 研究[异步任务架构](./02-core-architecture/async-task-architecture.md)
2. 理解[分布式系统](./05-advanced-features/distributed-systems.md)设计
3. 分析[认证和多租户](./05-advanced-features/auth-and-multi-tenancy-architecture.md)架构
4. 深入[技术细节](./06-technical-deep-dive/)实现原理

## 🔗 快速链接

- **GitHub 仓库**: [https://github.com/kortix-ai/suna](https://github.com/kortix-ai/suna)
- **Discord 社区**: [https://discord.gg/Py6pCBUUPw](https://discord.gg/Py6pCBUUPw)
- **问题反馈**: [GitHub Issues](https://github.com/kortix-ai/suna/issues)

## 📖 文档约定

- **代码示例**: 所有代码示例都经过测试验证
- **版本说明**: 文档基于 Suna 最新版本
- **更新标记**: 新增或更新的内容会特别标注
- **交叉引用**: 相关文档之间有明确的链接关系

## 🤝 贡献指南

欢迎贡献文档改进！请遵循以下原则：
- 保持文档结构清晰
- 添加实用的代码示例
- 更新相关的交叉引用
- 确保技术准确性

---

开始您的 Suna 之旅吧！如有任何问题，欢迎在社区中交流讨论。