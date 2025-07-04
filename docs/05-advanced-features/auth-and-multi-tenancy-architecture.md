# Suna 认证授权与多租户架构详解

## 目录
1. [概述](#概述)
2. [Supabase JWT 认证机制](#supabase-jwt-认证机制)
3. [Basejump 多租户框架](#basejump-多租户框架)
4. [Row Level Security (RLS) 策略](#row-level-security-rls-策略)
5. [团队管理和权限控制](#团队管理和权限控制)
6. [实际应用示例](#实际应用示例)
7. [最佳实践](#最佳实践)

## 概述

Suna 采用了一个强大而灵活的认证授权系统，基于以下核心技术构建：

- **Supabase Auth**：提供 JWT 令牌生成和用户管理
- **Basejump 框架**：实现多租户账户体系和团队协作
- **PostgreSQL RLS**：在数据库层面实现细粒度权限控制
- **FastAPI 依赖注入**：在应用层进行权限验证

这个系统支持个人账户和团队账户，提供了完整的多租户隔离和灵活的权限管理。

## Supabase JWT 认证机制

### JWT 令牌结构

Supabase 生成的 JWT 令牌包含以下关键信息：

```json
{
  "sub": "user-uuid",          // 用户唯一标识符
  "email": "user@example.com", // 用户邮箱
  "role": "authenticated",     // 用户角色
  "aud": "authenticated",      // 受众
  "exp": 1234567890,          // 过期时间
  "iat": 1234567890           // 签发时间
}
```

### 认证实现 (auth_utils.py)

```python
def decode_jwt(token: str) -> dict:
    """解码 JWT 令牌但不验证签名"""
    try:
        # 不验证签名，依赖 Supabase RLS 进行实际验证
        return jwt.decode(token, options={
            "verify_signature": False,
            "verify_exp": True,
            "verify_aud": False
        })
    except Exception as e:
        raise HTTPException(401, "Invalid token")

def get_current_user_id_from_jwt(
    authorization: Optional[str] = Header(None),
    auth: Optional[str] = Query(None)
) -> str:
    """从请求中提取并验证用户 ID"""
    # 优先从 Authorization 头获取
    if authorization and authorization.startswith("Bearer "):
        access_token = authorization.split(" ")[1]
    # 备选：从查询参数获取（用于 SSE）
    elif auth:
        access_token = auth
    else:
        raise HTTPException(401, "Missing authentication")
    
    payload = decode_jwt(access_token)
    return payload.get("sub")
```

### 三种认证模式

1. **标准认证**：所有常规 API 端点
```python
@app.post("/api/threads")
async def create_thread(
    user_id: str = Depends(get_current_user_id_from_jwt)
):
    # 用户已认证
```

2. **流式认证**：SSE 端点的特殊处理
```python
@app.get("/api/stream/{run_id}")
async def stream_endpoint(
    run_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt_stream)
):
    # 支持从查询参数获取令牌
```

3. **可选认证**：公开资源的灵活访问
```python
@app.get("/api/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    user_id: Optional[str] = Depends(get_current_user_id_from_jwt_optional)
):
    # 用户可能已认证或匿名
```

## Basejump 多租户框架

### 核心概念

Basejump 提供了一个完整的 SaaS 多租户解决方案：

1. **账户类型**
   - **个人账户**：用户注册时自动创建
   - **团队账户**：多用户协作，支持角色管理

2. **用户角色**
   - **Owner**：账户所有者，拥有全部权限
   - **Member**：团队成员，拥有使用权限

### 数据库架构

```sql
-- 账户表
CREATE TABLE basejump.accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text,
    slug text UNIQUE,
    personal_account boolean DEFAULT false,
    primary_owner_user_id uuid REFERENCES auth.users(id),
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 账户用户关系表
CREATE TABLE basejump.account_user (
    account_id uuid REFERENCES basejump.accounts(id),
    user_id uuid REFERENCES auth.users(id),
    account_role basejump.account_role DEFAULT 'member',
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (account_id, user_id)
);

-- 邀请表
CREATE TABLE basejump.invitations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id uuid REFERENCES basejump.accounts(id),
    token text UNIQUE DEFAULT generate_token(30),
    invited_by_user_id uuid REFERENCES auth.users(id),
    email text,
    account_role basejump.account_role DEFAULT 'member',
    created_at timestamptz DEFAULT now(),
    expires_at timestamptz DEFAULT now() + interval '24 hours'
);
```

### 核心函数

```sql
-- 检查用户在账户中的角色
CREATE FUNCTION basejump.has_role_on_account(
    account_id uuid,
    account_role basejump.account_role DEFAULT NULL
) RETURNS boolean AS $$
BEGIN
    IF account_role IS NULL THEN
        -- 检查用户是否属于账户
        RETURN EXISTS(
            SELECT 1 FROM basejump.account_user au
            WHERE au.account_id = has_role_on_account.account_id
            AND au.user_id = auth.uid()
        );
    ELSE
        -- 检查用户是否有特定角色
        RETURN EXISTS(
            SELECT 1 FROM basejump.account_user au
            WHERE au.account_id = has_role_on_account.account_id
            AND au.user_id = auth.uid()
            AND au.account_role = has_role_on_account.account_role
        );
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 获取用户所属的账户列表
CREATE FUNCTION basejump.get_accounts_with_role(
    passed_in_role basejump.account_role DEFAULT NULL
) RETURNS SETOF basejump.accounts AS $$
    SELECT a.*
    FROM basejump.accounts a
    JOIN basejump.account_user au ON a.id = au.account_id
    WHERE au.user_id = auth.uid()
    AND (
        passed_in_role IS NULL 
        OR au.account_role = passed_in_role
    );
$$ LANGUAGE sql SECURITY DEFINER;
```

## Row Level Security (RLS) 策略

### RLS 的工作原理

RLS 在数据库层面实现权限控制，每次查询都会自动应用相应的策略：

```sql
-- 启用 RLS
ALTER TABLE threads ENABLE ROW LEVEL SECURITY;

-- 创建策略
CREATE POLICY policy_name ON table_name
FOR operation  -- SELECT, INSERT, UPDATE, DELETE, ALL
USING (condition)  -- 查询条件
WITH CHECK (condition);  -- 写入条件
```

### 主要表的 RLS 策略实现

#### 1. threads 表策略

```sql
-- 查询策略：用户可以访问自己账户的线程或公开线程
CREATE POLICY thread_select_policy ON threads
FOR SELECT
USING (
    -- 线程是公开的
    is_public IS TRUE
    -- 或用户属于线程所属账户
    OR basejump.has_role_on_account(account_id) = true
    -- 或线程所属项目是公开的/用户有权访问
    OR EXISTS (
        SELECT 1 FROM projects
        WHERE projects.project_id = threads.project_id
        AND (
            projects.is_public IS TRUE
            OR basejump.has_role_on_account(projects.account_id) = true
        )
    )
);

-- 创建策略：只能在自己的账户下创建线程
CREATE POLICY thread_insert_policy ON threads
FOR INSERT
WITH CHECK (
    basejump.has_role_on_account(account_id) = true
);

-- 更新策略：只能更新自己账户的线程
CREATE POLICY thread_update_policy ON threads
FOR UPDATE
USING (basejump.has_role_on_account(account_id) = true)
WITH CHECK (basejump.has_role_on_account(account_id) = true);
```

#### 2. agents 表策略

```sql
-- 查询：账户成员可以查看
CREATE POLICY agents_select_own ON agents
    FOR SELECT
    USING (basejump.has_role_on_account(account_id));

-- 创建/更新/删除：只有 owner 可以操作
CREATE POLICY agents_insert_own ON agents
    FOR INSERT
    WITH CHECK (basejump.has_role_on_account(account_id, 'owner'));

CREATE POLICY agents_update_own ON agents
    FOR UPDATE
    USING (basejump.has_role_on_account(account_id, 'owner'))
    WITH CHECK (basejump.has_role_on_account(account_id, 'owner'));

CREATE POLICY agents_delete_own ON agents
    FOR DELETE
    USING (basejump.has_role_on_account(account_id, 'owner'));
```

#### 3. knowledge_base_entries 表策略

```sql
-- 复杂的权限继承：通过线程或项目的权限
CREATE POLICY kb_entries_user_access ON knowledge_base_entries
    FOR ALL
    USING (
        -- 检查通过线程的权限
        EXISTS (
            SELECT 1 FROM threads t
            LEFT JOIN projects p ON t.project_id = p.project_id
            WHERE t.thread_id = knowledge_base_entries.thread_id
            AND (
                -- 用户有线程账户权限
                basejump.has_role_on_account(t.account_id) = true OR 
                -- 或有项目账户权限
                basejump.has_role_on_account(p.account_id) = true OR
                -- 或有知识库条目账户权限
                basejump.has_role_on_account(knowledge_base_entries.account_id) = true
            )
        )
    );
```

## 团队管理和权限控制

### 团队创建流程

1. **创建团队账户**
```sql
-- 通过 RPC 创建团队
SELECT basejump.create_account(
    slug := 'my-team',
    name := 'My Team'
);
```

2. **邀请团队成员**
```sql
-- 创建邀请
SELECT basejump.create_invitation(
    account_id := 'team-uuid',
    email := 'member@example.com',
    role := 'member'
);
```

3. **接受邀请**
```sql
-- 被邀请者接受邀请
SELECT basejump.accept_invitation('invitation-token');
```

### 前端权限管理组件

#### AccountSelector 组件
```tsx
// 账户切换器
export function AccountSelector() {
  const { data: accounts } = useAccounts();
  const { currentAccount, setCurrentAccount } = useAuth();
  
  return (
    <Select value={currentAccount.id} onValueChange={setCurrentAccount}>
      {accounts.map(account => (
        <SelectItem key={account.id} value={account.id}>
          {account.personal_account ? "Personal" : account.name}
        </SelectItem>
      ))}
    </Select>
  );
}
```

#### 团队成员管理
```tsx
// 管理团队成员
export function ManageTeamMembers({ accountId }) {
  const { data: members } = useTeamMembers(accountId);
  
  return (
    <Table>
      {members.map(member => (
        <TableRow key={member.user_id}>
          <TableCell>{member.email}</TableCell>
          <TableCell>{member.account_role}</TableCell>
          <TableCell>
            {member.account_role === 'member' && (
              <Button onClick={() => updateRole(member.user_id, 'owner')}>
                Make Owner
              </Button>
            )}
          </TableCell>
        </TableRow>
      ))}
    </Table>
  );
}
```

### 后端权限验证

```python
async def verify_thread_access(
    thread_id: str, 
    user_id: str, 
    supabase_client
) -> dict:
    """验证用户对线程的访问权限"""
    # 查询线程信息，RLS 自动应用
    thread_response = await supabase_client.table("threads") \
        .select("*, projects(*)") \
        .eq("thread_id", thread_id) \
        .single() \
        .execute()
    
    if not thread_response.data:
        # RLS 阻止了访问
        raise HTTPException(403, "Access denied")
    
    return thread_response.data

async def get_account_id_from_thread(
    thread_id: str,
    supabase_client
) -> str:
    """获取线程关联的账户 ID"""
    thread = await verify_thread_access(thread_id, user_id, supabase_client)
    
    # 优先使用线程账户，其次使用项目账户
    return thread.get("account_id") or thread["projects"]["account_id"]
```

## 实际应用示例

### 示例 1：创建私有线程

```python
# API 端点
@app.post("/api/threads")
async def create_thread(
    request: CreateThreadRequest,
    user_id: str = Depends(get_current_user_id_from_jwt)
):
    # 获取用户当前账户
    account_id = request.account_id
    
    # 创建线程（RLS 会验证权限）
    thread = await supabase.table("threads").insert({
        "title": request.title,
        "account_id": account_id,
        "is_public": False
    }).execute()
    
    return thread.data
```

### 示例 2：团队协作场景

```python
# 团队成员使用团队的 Agent
@app.post("/api/agents/{agent_id}/run")
async def run_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
):
    # 查询 Agent（RLS 确保用户有权访问）
    agent = await supabase.table("agents") \
        .select("*") \
        .eq("agent_id", agent_id) \
        .single() \
        .execute()
    
    if not agent.data:
        raise HTTPException(403, "Agent not found or access denied")
    
    # 执行 Agent
    return await execute_agent(agent.data)
```

### 示例 3：公开项目访问

```python
# 支持匿名访问的端点
@app.get("/api/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    user_id: Optional[str] = Depends(get_current_user_id_from_jwt_optional)
):
    if user_id:
        # 认证用户：使用其凭证查询
        client = await create_user_client(user_id)
    else:
        # 匿名用户：使用 anon key
        client = create_anon_client()
    
    # 查询线程（RLS 会处理公开/私有逻辑）
    thread = await client.table("threads") \
        .select("*") \
        .eq("thread_id", thread_id) \
        .single() \
        .execute()
    
    return thread.data
```

## 最佳实践

### 1. 安全性最佳实践

- **永远不要在客户端验证签名**：让 Supabase 处理 JWT 验证
- **使用 RLS 作为主要防线**：应用层验证只是辅助
- **最小权限原则**：默认拒绝，明确授权
- **审计日志**：记录敏感操作

### 2. 性能优化

```sql
-- 为常用查询创建索引
CREATE INDEX idx_account_user_lookup 
ON basejump.account_user(user_id, account_id);

CREATE INDEX idx_threads_account 
ON threads(account_id) 
WHERE is_public = false;

-- 使用部分索引优化公开内容查询
CREATE INDEX idx_public_threads 
ON threads(thread_id) 
WHERE is_public = true;
```

### 3. 错误处理

```python
class AuthError(Exception):
    """认证相关错误"""
    pass

class PermissionError(Exception):
    """权限相关错误"""
    pass

# 统一错误处理
@app.exception_handler(AuthError)
async def auth_error_handler(request, exc):
    return JSONResponse(
        status_code=401,
        content={"error": "Authentication required"}
    )

@app.exception_handler(PermissionError)
async def permission_error_handler(request, exc):
    return JSONResponse(
        status_code=403,
        content={"error": "Permission denied"}
    )
```

### 4. 测试策略

```python
# 测试不同角色的访问权限
async def test_owner_can_manage_agents():
    # 作为 owner 登录
    client = create_test_client(role="owner")
    
    # 应该能创建 agent
    response = await client.post("/api/agents", json={...})
    assert response.status_code == 200

async def test_member_cannot_delete_agents():
    # 作为 member 登录
    client = create_test_client(role="member")
    
    # 不应该能删除 agent
    response = await client.delete("/api/agents/123")
    assert response.status_code == 403
```

## 总结

Suna 的认证授权系统通过以下层次提供安全保障：

1. **Supabase Auth**：处理用户认证和 JWT 生成
2. **Basejump 框架**：提供多租户账户管理
3. **PostgreSQL RLS**：在数据库层实施权限控制
4. **应用层验证**：额外的业务逻辑验证

这个架构确保了：
- ✅ 完全的多租户隔离
- ✅ 灵活的团队协作
- ✅ 细粒度的权限控制
- ✅ 高性能和可扩展性
- ✅ 支持公开内容共享

通过这种设计，Suna 能够同时服务个人用户和企业团队，提供安全、可靠的 AI 助手服务。