#!/usr/bin/env python3
"""
用户管理工具
提供完整的用户管理功能，包括创建、列出、查看和删除用户

使用方法:
    # 列出所有用户
    python manage_users.py list
    
    # 创建新用户
    python manage_users.py create <email> <password>
    
    # 查看用户详情
    python manage_users.py info <user_id_or_email>
    
    # 删除用户
    python manage_users.py delete <user_id>
"""

import asyncio
import sys
import os
import json
from typing import Optional, List, Dict
from datetime import datetime
from dotenv import load_dotenv

# 确保导入路径正确
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client, Client
from utils.config import config
from utils.logger import logger

class UserManager:
    """用户管理类"""
    
    def __init__(self):
        """初始化用户管理器"""
        self.client = self._get_supabase_client()
    
    def _get_supabase_client(self) -> Client:
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
    
    def list_users(self, limit: int = 50) -> List[Dict]:
        """
        列出所有用户
        
        Args:
            limit: 返回的最大用户数
            
        Returns:
            List[Dict]: 用户列表
        """
        try:
            # 使用 Admin API 列出用户
            response = self.client.auth.admin.list_users(page=1, per_page=limit)
            users = response.users
            
            # 获取每个用户的账户信息
            for user in users:
                accounts = self.client.table("account_user").select("*").eq("user_id", user.id).execute()
                user.accounts = accounts.data if accounts.data else []
            
            return users
            
        except Exception as e:
            logger.error(f"获取用户列表失败: {str(e)}")
            raise
    
    def create_user(self, email: str, password: str, metadata: Optional[Dict] = None) -> Dict:
        """
        创建新用户
        
        Args:
            email: 用户邮箱
            password: 用户密码
            metadata: 可选的用户元数据
            
        Returns:
            Dict: 创建的用户信息
        """
        try:
            user_data = {
                "email": email,
                "password": password,
                "email_confirm": True  # 自动确认邮箱
            }
            
            if metadata:
                user_data["user_metadata"] = metadata
            
            response = self.client.auth.admin.create_user(user_data)
            user = response.user
            
            # 获取账户信息
            accounts = self.client.table("account_user").select("*").eq("user_id", user.id).execute()
            
            return {
                "id": user.id,
                "email": user.email,
                "created_at": user.created_at,
                "metadata": user.user_metadata,
                "accounts": accounts.data if accounts.data else []
            }
            
        except Exception as e:
            logger.error(f"创建用户失败: {str(e)}")
            raise
    
    def get_user_info(self, user_identifier: str) -> Optional[Dict]:
        """
        获取用户详细信息
        
        Args:
            user_identifier: 用户ID或邮箱
            
        Returns:
            Optional[Dict]: 用户信息，如果未找到则返回 None
        """
        try:
            # 尝试通过 ID 获取
            if "@" not in user_identifier:
                response = self.client.auth.admin.get_user_by_id(user_identifier)
                user = response.user
            else:
                # 通过邮箱获取
                users = self.client.auth.admin.list_users()
                user = None
                for u in users.users:
                    if u.email == user_identifier:
                        user = u
                        break
                
                if not user:
                    return None
            
            # 获取账户信息
            accounts = self.client.table("account_user").select("*, accounts(*)").eq("user_id", user.id).execute()
            
            # 获取线程信息
            threads = self.client.table("threads").select("id, name, created_at, updated_at").eq("account_id", user.id).execute()
            
            return {
                "id": user.id,
                "email": user.email,
                "created_at": user.created_at,
                "last_sign_in": user.last_sign_in_at,
                "metadata": user.user_metadata,
                "accounts": accounts.data if accounts.data else [],
                "threads_count": len(threads.data) if threads.data else 0,
                "recent_threads": threads.data[:5] if threads.data else []
            }
            
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return None
    
    def delete_user(self, user_id: str) -> bool:
        """
        删除用户
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 是否成功删除
        """
        try:
            # 使用 Admin API 删除用户
            self.client.auth.admin.delete_user(user_id)
            logger.info(f"成功删除用户: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除用户失败: {str(e)}")
            return False

def format_datetime(dt_str: Optional[str]) -> str:
    """格式化日期时间字符串"""
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return dt_str

def print_user_list(users: List):
    """打印用户列表"""
    print(f"\n📋 找到 {len(users)} 个用户:\n")
    print(f"{'ID':<38} {'邮箱':<30} {'创建时间':<20} {'账户数':<8}")
    print("-" * 100)
    
    for user in users:
        account_count = len(user.accounts) if hasattr(user, 'accounts') else 0
        print(f"{user.id:<38} {user.email:<30} {format_datetime(user.created_at):<20} {account_count:<8}")

def print_user_details(user_info: Dict):
    """打印用户详细信息"""
    print(f"\n👤 用户详情:")
    print(f"{'='*50}")
    print(f"ID: {user_info['id']}")
    print(f"邮箱: {user_info['email']}")
    print(f"创建时间: {format_datetime(user_info['created_at'])}")
    print(f"最后登录: {format_datetime(user_info['last_sign_in'])}")
    
    if user_info.get('metadata'):
        print(f"\n元数据:")
        print(json.dumps(user_info['metadata'], indent=2, ensure_ascii=False))
    
    if user_info.get('accounts'):
        print(f"\n关联账户 ({len(user_info['accounts'])}):")
        for acc in user_info['accounts']:
            print(f"  - 账户ID: {acc['account_id']}")
            print(f"    角色: {acc['account_role']}")
            if acc.get('accounts'):
                print(f"    名称: {acc['accounts'].get('name', 'N/A')}")
    
    print(f"\n线程总数: {user_info['threads_count']}")
    
    if user_info.get('recent_threads'):
        print(f"\n最近的线程:")
        for thread in user_info['recent_threads']:
            print(f"  - {thread['name'] or '未命名'} (ID: {thread['id'][:8]}...)")
            print(f"    创建于: {format_datetime(thread['created_at'])}")

def main():
    """主函数"""
    # 加载环境变量
    load_dotenv()
    
    # 检查参数
    if len(sys.argv) < 2:
        print("用户管理工具")
        print("\n使用方法:")
        print("  python manage_users.py list                    - 列出所有用户")
        print("  python manage_users.py create <email> <pwd>    - 创建新用户")
        print("  python manage_users.py info <id_or_email>      - 查看用户详情")
        print("  python manage_users.py delete <user_id>        - 删除用户")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    manager = UserManager()
    
    try:
        if command == "list":
            users = manager.list_users()
            print_user_list(users)
            
        elif command == "create":
            if len(sys.argv) < 4:
                print("错误: 需要提供邮箱和密码")
                print("使用方法: python manage_users.py create <email> <password>")
                sys.exit(1)
            
            email = sys.argv[2]
            password = sys.argv[3]
            
            if "@" not in email:
                print("错误: 无效的邮箱地址")
                sys.exit(1)
            
            if len(password) < 6:
                print("错误: 密码长度至少需要 6 个字符")
                sys.exit(1)
            
            user_info = manager.create_user(email, password)
            print(f"\n✅ 用户创建成功!")
            print(f"用户ID: {user_info['id']}")
            print(f"邮箱: {user_info['email']}")
            
        elif command == "info":
            if len(sys.argv) < 3:
                print("错误: 需要提供用户ID或邮箱")
                print("使用方法: python manage_users.py info <user_id_or_email>")
                sys.exit(1)
            
            user_identifier = sys.argv[2]
            user_info = manager.get_user_info(user_identifier)
            
            if user_info:
                print_user_details(user_info)
            else:
                print(f"❌ 未找到用户: {user_identifier}")
            
        elif command == "delete":
            if len(sys.argv) < 3:
                print("错误: 需要提供用户ID")
                print("使用方法: python manage_users.py delete <user_id>")
                sys.exit(1)
            
            user_id = sys.argv[2]
            
            # 确认删除
            print(f"⚠️  确定要删除用户 {user_id} 吗？")
            print("这将永久删除用户及其所有数据。")
            confirm = input("输入 'yes' 确认删除: ")
            
            if confirm.lower() == 'yes':
                if manager.delete_user(user_id):
                    print("✅ 用户已删除")
                else:
                    print("❌ 删除失败")
            else:
                print("取消删除操作")
        
        else:
            print(f"错误: 未知命令 '{command}'")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"操作失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()