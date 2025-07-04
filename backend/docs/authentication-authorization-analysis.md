# Suna 项目认证授权系统分析报告

## 概述

Suna 项目采用了基于 Supabase 的认证授权体系，结合 JWT 令牌验证和行级安全（RLS）策略，实现了完整的用户认证和权限控制系统。

## 1. 认证系统架构

### 1.1 JWT 认证机制

**核心文件**: `/backend/utils/auth_utils.py`

主要功能：
- **JWT 令牌解析**：从 HTTP Authorization 头或查询参数中提取 JWT 令牌
- **用户身份验证**：从 JWT 的 `sub` claim 中提取用户 ID
- **无签名验证**：使用 `verify_signature=False` 选项，依赖 Supabase 的 RLS 进行实际验证

关键函数：
```python
# 标准认证装饰器
async def get_current_user_id_from_jwt(request: Request) -> str

# 流式端点认证（支持 EventSource）
async def get_user_id_from_stream_auth(request: Request, token: Optional[str] = None) -> str

# 可选认证（用于公开项目）
async def get_optional_user_id(request: Request) -> Optional[str]
```

### 1.2 Supabase 客户端配置

**核心文件**: `/backend/services/supabase.py`

- 使用单例模式管理数据库连接
- 优先使用 Service Role Key（具有更高权限）
- 支持异步操作
- 提供图片上传等额外功能

## 2. 账户和权限模型

### 2.1 Basejump 账户系统

**核心表结构**：
- `basejump.accounts` - 账户主表
- `basejump.account_user` - 用户与账户的关联表
- `basejump.account_role` - 账户角色枚举（owner, member）

**账户类型**：
- **个人账户** (`personal_account = true`)：每个用户自动创建
- **团队账户** (`personal_account = false`)：支持多用户协作

### 2.2 权限角色

- **Owner**：账户所有者，可以管理成员、修改账户信息、处理计费
- **Member**：普通成员，可以访问账户资源但不能管理账户

## 3. 行级安全（RLS）策略

### 3.1 账户访问控制

```sql
-- 账户可被成员查看
CREATE POLICY "Accounts are viewable by members" ON basejump.accounts
    FOR SELECT
    USING (basejump.has_role_on_account(id) = true);

-- 账户可被所有者编辑
CREATE POLICY "Accounts can be edited by owners" ON basejump.accounts
    FOR UPDATE
    USING (basejump.has_role_on_account(id, 'owner') = true);
```

### 3.2 线程（Thread）访问控制

```sql
CREATE POLICY thread_select_policy ON threads
    FOR SELECT
    USING (
        -- 公开线程
        is_public IS TRUE
        -- 或用户是账户成员
        OR basejump.has_role_on_account(account_id) = true
        -- 或通过项目访问
        OR EXISTS (
            SELECT 1 FROM projects
            WHERE projects.project_id = threads.project_id
            AND (projects.is_public = TRUE OR basejump.has_role_on_account(projects.account_id) = true)
        )
    );
```

### 3.3 消息（Message）访问控制

消息的访问权限继承自其所属的线程权限。

## 4. API 端点认证

### 4.1 认证装饰器使用

所有需要认证的 API 端点都使用 FastAPI 的依赖注入系统：

```python
@router.post("/thread/{thread_id}/agent/start")
async def start_agent(
    thread_id: str,
    body: AgentStartRequest = Body(...),
    user_id: str = Depends(get_current_user_id_from_jwt)
):
```

### 4.2 权限验证流程

1. **提取用户 ID**：通过 JWT 装饰器获取当前用户
2. **验证线程访问**：调用 `verify_thread_access()` 检查用户权限
3. **检查账户成员资格**：通过 RLS 或手动查询验证
4. **处理公开资源**：支持公开项目和线程的匿名访问

## 5. 特殊认证场景

### 5.1 流式端点认证

支持通过查询参数传递令牌，适用于 EventSource 等无法设置请求头的场景：

```python
async def get_user_id_from_stream_auth(
    request: Request,
    token: Optional[str] = None
) -> str
```

### 5.2 内部用户访问

为 `@kortix.ai` 邮箱域的内部用户提供只读访问权限：

```sql
CREATE POLICY "Give read only access to internal users" ON threads
FOR SELECT
USING (
    ((auth.jwt() ->> 'email'::text) ~~ '%@kortix.ai'::text)
);
```

## 6. 安全特性

### 6.1 防护措施

- **HTTP 401 响应**：未认证请求返回标准 401 状态码
- **WWW-Authenticate 头**：包含 Bearer 认证方案提示
- **错误处理**：详细的错误信息用于调试，生产环境应谨慎暴露

### 6.2 上下文绑定

使用 Sentry 和 structlog 记录用户上下文：

```python
sentry.sentry.set_user({"id": user_id})
structlog.contextvars.bind_contextvars(user_id=user_id)
```

## 7. 主要 API 端点认证情况

### 需要认证的端点：
- `/thread/{thread_id}/agent/start` - 启动代理
- `/agent-run/{agent_run_id}/stop` - 停止代理运行
- `/thread/{thread_id}/agent-runs` - 获取代理运行历史
- `/agents` - 管理自定义代理
- `/agents/{agent_id}/publish` - 发布代理到市场

### 支持可选认证的端点：
- 公开项目和线程的访问端点

## 8. 权限检查辅助函数

- `basejump.has_role_on_account()` - 检查用户在账户中的角色
- `verify_thread_access()` - 验证线程访问权限
- `get_account_id_from_thread()` - 从线程获取账户 ID

## 9. 建议和注意事项

1. **JWT 签名验证**：当前代码未验证 JWT 签名，依赖 Supabase RLS。在生产环境中应考虑添加签名验证
2. **错误信息泄露**：某些错误信息包含内部细节，生产环境应使用通用错误消息
3. **权限缓存**：频繁的权限检查可能影响性能，可考虑添加缓存层
4. **审计日志**：建议添加权限检查的审计日志，便于安全审查

## 总结

Suna 项目的认证授权系统设计合理，充分利用了 Supabase 的 RLS 功能，实现了灵活的多租户权限控制。系统支持个人账户和团队协作，并通过 JWT 和数据库级别的安全策略提供了多层防护。