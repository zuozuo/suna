# 用户管理脚本说明

本目录包含用于管理 Suna 系统用户的脚本。

## 前置要求

1. 确保已配置好 `backend/.env` 文件，特别是以下变量：
   - `SUPABASE_URL`: Supabase 项目 URL
   - `SUPABASE_SERVICE_ROLE_KEY`: Service Role 密钥（必需，用于创建用户）
   - `SUPABASE_ANON_KEY`: Anon 密钥

2. 安装好项目依赖：
   ```bash
   cd backend
   uv sync
   ```

## 脚本说明

### 1. create_test_user.py - 创建测试用户

快速创建一个测试用户。

**使用方法：**
```bash
cd backend
python utils/scripts/create_test_user.py <email> <password>
```

**示例：**
```bash
python utils/scripts/create_test_user.py test@example.com password123
```

**功能：**
- 创建一个新用户
- 自动确认邮箱
- 显示创建的用户信息和关联的个人账户

### 2. manage_users.py - 综合用户管理

提供完整的用户管理功能。

**列出所有用户：**
```bash
python utils/scripts/manage_users.py list
```

**创建新用户：**
```bash
python utils/scripts/manage_users.py create <email> <password>
```

**查看用户详情：**
```bash
# 通过用户 ID
python utils/scripts/manage_users.py info <user_id>

# 通过邮箱
python utils/scripts/manage_users.py info test@example.com
```

**删除用户：**
```bash
python utils/scripts/manage_users.py delete <user_id>
```

⚠️ **注意**：删除用户会同时删除：
- 用户的所有账户（仅个人账户）
- 账户下的所有项目
- 所有对话线程和消息

## 用户系统说明

### 用户创建流程

1. 当创建新用户时，系统会自动触发 `basejump.run_new_user_setup()` 函数
2. 该函数会：
   - 创建一个个人账户（personal_account = true）
   - 账户 ID 与用户 ID 相同
   - 账户名称默认为邮箱 @ 符号前的部分
   - 将用户添加到 `account_user` 表，角色为 `owner`

### 数据库表结构

**auth.users** (Supabase 内置)
- id: 用户唯一标识
- email: 用户邮箱
- created_at: 创建时间
- last_sign_in_at: 最后登录时间

**basejump.accounts**
- id: 账户 ID
- primary_owner_user_id: 主要所有者
- name: 账户名称
- slug: 账户标识（个人账户为空）
- personal_account: 是否为个人账户

**basejump.account_user**
- user_id: 用户 ID
- account_id: 账户 ID
- account_role: 用户角色（owner/member）

## 常见问题

### 1. 创建用户失败

**可能原因：**
- 缺少 `SUPABASE_SERVICE_ROLE_KEY`
- 邮箱已被使用
- 密码不符合要求（至少6个字符）

### 2. 用户创建成功但无法登录

**检查事项：**
- 确认前端配置的 Supabase URL 和 Anon Key 正确
- 检查 Supabase 项目的认证设置
- 确认邮箱验证设置

### 3. 删除用户失败

**可能原因：**
- 用户是团队账户的成员（需要先移除）
- 有其他用户依赖的数据

## 测试用户最佳实践

1. **开发环境**：使用 `test@example.com`、`dev@example.com` 等明显的测试邮箱
2. **密码管理**：使用安全但易记的密码，如 `Test123!@#`
3. **定期清理**：使用 `manage_users.py list` 查看并清理不需要的测试用户

## 扩展功能

如需添加更多功能，可以参考现有脚本结构：

1. 批量创建用户
2. 导入/导出用户数据
3. 重置用户密码
4. 管理用户权限

## 安全提醒

- **Service Role Key** 具有完全的数据库访问权限，请妥善保管
- 这些脚本仅应在开发/测试环境使用
- 生产环境的用户管理应通过应用程序界面进行