#!/usr/bin/env python3
"""
创建测试用户的脚本
用于在本地开发环境快速创建 Supabase 测试用户

使用方法:
    python create_test_user.py <email> <password>
    
示例:
    python create_test_user.py test@example.com password123
"""

import asyncio
import sys
import os
from typing import Optional
from dotenv import load_dotenv

# 确保导入路径正确
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client, Client
from utils.config import config
from utils.logger import logger

def get_supabase_client() -> Client:
    """获取 Supabase 客户端实例"""
    supabase_url = config.SUPABASE_URL
    supabase_key = config.SUPABASE_SERVICE_ROLE_KEY
    
    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "缺少必要的环境变量。请确保 .env 文件中设置了:\n"
            "- SUPABASE_URL\n"
            "- SUPABASE_SERVICE_ROLE_KEY"
        )
    
    return create_client(supabase_url, supabase_key)

def create_user(email: str, password: str) -> dict:
    """
    创建新用户
    
    Args:
        email: 用户邮箱
        password: 用户密码
        
    Returns:
        dict: 创建的用户信息
    """
    client = get_supabase_client()
    
    try:
        # 使用 Admin API 创建用户
        response = client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True  # 自动确认邮箱
        })
        
        user = response.user
        logger.info(f"成功创建用户: {user.email} (ID: {user.id})")
        
        # 查询用户的账户信息
        accounts = client.table("account_user").select("*").eq("user_id", user.id).execute()
        
        if accounts.data:
            logger.info(f"用户关联账户:")
            for account in accounts.data:
                logger.info(f"  - 账户ID: {account['account_id']}, 角色: {account['account_role']}")
        
        return {
            "id": user.id,
            "email": user.email,
            "created_at": user.created_at,
            "accounts": accounts.data if accounts.data else []
        }
        
    except Exception as e:
        logger.error(f"创建用户失败: {str(e)}")
        
        # 检查是否是因为用户已存在
        if "already been registered" in str(e):
            logger.info("尝试获取现有用户信息...")
            try:
                # 尝试获取用户信息
                users = client.table("auth.users").select("*").eq("email", email).execute()
                if users.data:
                    user = users.data[0]
                    logger.info(f"找到现有用户: {user['email']} (ID: {user['id']})")
                    return {
                        "id": user['id'],
                        "email": user['email'],
                        "created_at": user.get('created_at'),
                        "existing": True
                    }
            except:
                pass
        
        raise

def main():
    """主函数"""
    # 加载环境变量
    load_dotenv()
    
    # 检查参数
    if len(sys.argv) != 3:
        print("使用方法: python create_test_user.py <email> <password>")
        print("示例: python create_test_user.py test@example.com password123")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    # 验证输入
    if "@" not in email:
        logger.error("无效的邮箱地址")
        sys.exit(1)
    
    if len(password) < 6:
        logger.error("密码长度至少需要 6 个字符")
        sys.exit(1)
    
    try:
        # 创建用户
        user_info = create_user(email, password)
        
        print("\n✅ 用户创建成功!")
        print(f"邮箱: {user_info['email']}")
        print(f"用户ID: {user_info['id']}")
        
        if user_info.get('existing'):
            print("(这是一个已存在的用户)")
        
        print("\n您现在可以使用这个账户登录系统。")
        
    except Exception as e:
        logger.error(f"操作失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()