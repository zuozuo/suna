#!/usr/bin/env python
"""
创建测试用户的脚本

使用方法:
    python create_test_user.py <email> <password>
    
示例:
    python create_test_user.py test@example.com mypassword123
    
注意：
- 需要先配置好 .env 文件中的 Supabase 连接信息
- 需要使用 SUPABASE_SERVICE_ROLE_KEY 来创建用户
"""

import asyncio
import sys
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client
import json

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

# 导入项目依赖
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from services.supabase import DBConnection
from utils.logger import logger


def get_sync_client() -> Client:
    """获取同步的 Supabase 客户端（用于创建用户）"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_key:
        raise ValueError("缺少必要的环境变量：SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    
    return create_client(supabase_url, supabase_service_key)


async def get_user_info(user_id: str) -> Optional[Dict[str, Any]]:
    """获取用户信息和关联的账户信息"""
    db = DBConnection()
    client = await db.client
    
    # 查询用户的账户信息
    result = await client.schema('basejump').from_('account_user').select(
        'account_id, account_role, accounts!inner(id, name, slug, personal_account)'
    ).eq('user_id', user_id).execute()
    
    if result.data:
        return result.data
    return None


async def create_test_user(email: str, password: str) -> Dict[str, Any]:
    """
    创建测试用户
    
    Args:
        email: 用户邮箱
        password: 用户密码
        
    Returns:
        创建的用户信息
    """
    # 使用同步客户端创建用户（auth.admin 需要同步客户端）
    sync_client = get_sync_client()
    
    try:
        # 创建用户
        logger.info(f"正在创建用户: {email}")
        user_response = sync_client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True  # 自动确认邮箱
        })
        
        if not user_response or not user_response.user:
            raise Exception("创建用户失败：未返回用户信息")
        
        user = user_response.user
        logger.info(f"成功创建用户，ID: {user.id}")
        
        # 等待一下让触发器执行（创建个人账户）
        await asyncio.sleep(2)
        
        # 获取用户的账户信息
        user_accounts = await get_user_info(user.id)
        
        return {
            "user_id": user.id,
            "email": user.email,
            "created_at": user.created_at,
            "accounts": user_accounts
        }
        
    except Exception as e:
        logger.error(f"创建用户失败: {str(e)}")
        raise


async def main():
    """主函数"""
    if len(sys.argv) != 3:
        print(f"使用方法: python {sys.argv[0]} <email> <password>")
        print(f"示例: python {sys.argv[0]} test@example.com mypassword123")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    # 验证输入
    if "@" not in email:
        print("错误：请提供有效的邮箱地址")
        sys.exit(1)
    
    if len(password) < 6:
        print("错误：密码至少需要6个字符")
        sys.exit(1)
    
    # 打印环境信息
    print(f"Supabase URL: {os.getenv('SUPABASE_URL')}")
    print(f"环境模式: {os.getenv('ENV_MODE', '未设置')}")
    print("-" * 50)
    
    try:
        # 创建用户
        user_info = await create_test_user(email, password)
        
        # 打印用户信息
        print("\n✅ 用户创建成功！")
        print(f"用户 ID: {user_info['user_id']}")
        print(f"邮箱: {user_info['email']}")
        print(f"创建时间: {user_info['created_at']}")
        
        if user_info['accounts']:
            print("\n关联的账户:")
            for i, account in enumerate(user_info['accounts']):
                acc_info = account['accounts']
                print(f"{i+1}. 账户名称: {acc_info['name'] or '未命名'}")
                print(f"   账户 ID: {acc_info['id']}")
                print(f"   账户类型: {'个人账户' if acc_info['personal_account'] else '团队账户'}")
                print(f"   用户角色: {account['account_role']}")
                if acc_info.get('slug'):
                    print(f"   账户标识: {acc_info['slug']}")
        
        print("\n现在可以使用以下凭据登录:")
        print(f"邮箱: {email}")
        print(f"密码: {password}")
        
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        sys.exit(1)
    finally:
        # 清理数据库连接
        await DBConnection.disconnect()


if __name__ == "__main__":
    asyncio.run(main())