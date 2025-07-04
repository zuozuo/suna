# Suna 用户管理指南

本文档介绍如何在 Suna 项目中创建和管理测试用户。

## 前置要求

1. **环境配置**
   
   确保在 `backend/.env` 文件中设置了以下环境变量：
   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_ANON_KEY=your_anon_key
   SUPABASE_SERVICE_ROLE_KEY=your_service_role_key  # 创建用户必需
   ```
   
   > ⚠️ **重要**: 创建用户需要 `SUPABASE_SERVICE_ROLE_KEY`，这个密钥具有管理员权限，请妥善保管。

2. **安装依赖**
   
   ```bash
   cd backend
   uv sync  # 或 pip install -r requirements.txt
   ```

## 快速开始

### 创建测试用户

使用 `create_test_user.py` 快速创建测试用户：

```bash
cd backend
python create_test_user.py test@example.com password123
```

成功输出示例：
```
✅ 用户创建成功!
邮箱: test@example.com
用户ID: 123e4567-e89b-12d3-a456-426614174000

您现在可以使用这个账户登录系统。
```

### 完整用户管理

使用 `manage_users.py` 进行更多操作：

#### 1. 列出所有用户
```bash
python manage_users.py list
```

#### 2. 创建新用户
```bash
python manage_users.py create user@example.com password123
```

#### 3. 查看用户详情
```bash
# 通过用户ID查看
python manage_users.py info 123e4567-e89b-12d3-a456-426614174000

# 通过邮箱查看
python manage_users.py info user@example.com
```

#### 4. 删除用户
```bash
python manage_users.py delete 123e4567-e89b-12d3-a456-426614174000
```

## 用户系统架构

### 数据库结构

Suna 使用 Supabase Auth 管理用户认证，相关表结构：

1. **auth.users** - Supabase 内置用户表
   - `id`: 用户唯一标识
   - `email`: 用户邮箱
   - `created_at`: 创建时间
   - `last_sign_in_at`: 最后登录时间

2. **public.accounts** - 账户表
   - `id`: 账户ID（个人账户的ID与用户ID相同）
   - `name`: 账户名称
   - `slug`: 账户标识符

3. **public.account_user** - 用户-账户关联表
   - `user_id`: 用户ID
   - `account_id`: 账户ID
   - `account_role`: 用户角色（owner/member）

### 自动化流程

当新用户注册时，系统会自动：
1. 在 `auth.users` 表创建用户记录
2. 触发 `basejump.run_new_user_setup()` 函数
3. 创建个人账户（账户ID = 用户ID）
4. 在 `account_user` 表中添加关联记录，角色为 `owner`

## 常见问题

### Q: 为什么创建用户需要 SERVICE_ROLE_KEY？
A: Supabase 的 Admin API 需要服务角色密钥才能创建用户。这是为了安全考虑，防止未授权的用户创建。

### Q: 如何在生产环境创建用户？
A: 生产环境应该通过正常的注册流程创建用户，而不是使用这些脚本。这些脚本仅用于开发和测试。

### Q: 创建的用户可以立即登录吗？
A: 是的，脚本会自动确认用户邮箱（`email_confirm: true`），用户可以立即登录。

### Q: 如何修改用户密码？
A: 可以通过 Supabase Dashboard 或使用 Supabase Auth API 的密码重置功能。

### Q: 删除用户会删除相关数据吗？
A: 是的，由于数据库设置了级联删除，删除用户会同时删除其关联的账户、线程等数据。

## 安全注意事项

1. **保护 SERVICE_ROLE_KEY**: 这个密钥具有完全的数据库访问权限，切勿泄露或提交到版本控制。

2. **生产环境**: 这些脚本仅用于开发和测试，不要在生产环境使用。

3. **密码安全**: 测试时可以使用简单密码，但生产环境应使用强密码。

## 故障排除

### 环境变量未设置
```
RuntimeError: 缺少必要的环境变量...
```
解决：检查 `.env` 文件是否正确配置。

### 用户已存在
```
ERROR: User already registered
```
解决：使用不同的邮箱，或先删除现有用户。

### 权限错误
```
ERROR: permission denied for schema auth
```
解决：确保使用的是 SERVICE_ROLE_KEY 而不是 ANON_KEY。

## 相关文件

- `backend/create_test_user.py` - 快速创建测试用户
- `backend/manage_users.py` - 完整用户管理工具
- `backend/services/supabase.py` - Supabase 连接管理
- `backend/utils/auth_utils.py` - 认证工具函数
- `backend/supabase/migrations/` - 数据库迁移文件