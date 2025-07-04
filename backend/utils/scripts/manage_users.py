#!/usr/bin/env python
"""
用户管理脚本 - 列出、创建、删除用户

使用方法:
    # 列出所有用户
    python manage_users.py list
    
    # 创建新用户
    python manage_users.py create <email> <password>
    
    # 删除用户
    python manage_users.py delete <user_id>
    
    # 查看用户详情
    python manage_users.py info <user_id_or_email>
"""

import asyncio
import sys
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
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
    """获取同步的 Supabase 客户端"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_key:
        raise ValueError("缺少必要的环境变量：SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    
    return create_client(supabase_url, supabase_service_key)


async def list_users() -> List[Dict[str, Any]]:
    """列出所有用户"""
    sync_client = get_sync_client()
    
    try:
        # 获取所有用户
        response = sync_client.auth.admin.list_users()
        users = response.users if hasattr(response, 'users') else []
        
        # 获取每个用户的账户信息
        db = DBConnection()
        client = await db.client
        
        user_list = []
        for user in users:
            # 查询用户的账户信息
            account_result = await client.schema('basejump').from_('account_user').select(
                'account_id, account_role, accounts!inner(name, personal_account)'
            ).eq('user_id', user.id).execute()
            
            user_info = {
                'id': user.id,
                'email': user.email,
                'created_at': user.created_at,
                'last_sign_in_at': user.last_sign_in_at,
                'accounts': account_result.data if account_result.data else []
            }
            user_list.append(user_info)
        
        return user_list
        
    except Exception as e:
        logger.error(f"获取用户列表失败: {str(e)}")
        raise


async def get_user_details(user_identifier: str) -> Optional[Dict[str, Any]]:
    """获取用户详细信息（通过 ID 或邮箱）"""
    sync_client = get_sync_client()
    db = DBConnection()
    client = await db.client
    
    try:
        # 判断是 ID 还是邮箱
        if "@" in user_identifier:
            # 通过邮箱查找
            users = sync_client.auth.admin.list_users()
            user = None
            for u in users.users:
                if u.email == user_identifier:
                    user = u
                    break
            if not user:
                return None
        else:
            # 通过 ID 查找
            user = sync_client.auth.admin.get_user_by_id(user_identifier)
        
        if not user:
            return None
        
        # 获取账户信息
        account_result = await client.schema('basejump').from_('account_user').select(
            'account_id, account_role, accounts!inner(*)'
        ).eq('user_id', user.id).execute()
        
        # 获取项目信息
        project_result = await client.table('projects').select(
            'project_id, name, created_at'
        ).in_('account_id', [acc['account_id'] for acc in account_result.data]).execute()
        
        # 获取线程信息
        thread_result = await client.table('threads').select(
            'thread_id, name, created_at'
        ).in_('account_id', [acc['account_id'] for acc in account_result.data]).execute()
        
        return {
            'user': {
                'id': user.id,
                'email': user.email,
                'created_at': user.created_at,
                'last_sign_in_at': user.last_sign_in_at,
                'email_confirmed_at': user.email_confirmed_at,
                'phone': user.phone,
                'phone_confirmed_at': user.phone_confirmed_at,
            },
            'accounts': account_result.data,
            'projects': project_result.data,
            'threads': thread_result.data
        }
        
    except Exception as e:
        logger.error(f"获取用户详情失败: {str(e)}")
        raise


async def create_user(email: str, password: str) -> Dict[str, Any]:
    """创建新用户"""
    sync_client = get_sync_client()
    
    try:
        # 创建用户
        user_response = sync_client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True
        })
        
        if not user_response or not user_response.user:
            raise Exception("创建用户失败")
        
        user = user_response.user
        
        # 等待触发器执行
        await asyncio.sleep(2)
        
        # 获取用户详情
        return await get_user_details(user.id)
        
    except Exception as e:
        logger.error(f"创建用户失败: {str(e)}")
        raise


async def delete_user(user_id: str) -> bool:
    """删除用户（需要先删除相关数据）"""
    sync_client = get_sync_client()
    db = DBConnection()
    client = await db.client
    
    try:
        # 获取用户的账户
        account_result = await client.schema('basejump').from_('account_user').select(
            'account_id'
        ).eq('user_id', user_id).execute()
        
        account_ids = [acc['account_id'] for acc in account_result.data]
        
        if account_ids:
            # 删除相关数据（按依赖顺序）
            # 1. 删除消息
            await client.table('messages').delete().in_('thread_id', 
                (await client.table('threads').select('thread_id').in_('account_id', account_ids).execute()).data
            ).execute()
            
            # 2. 删除线程
            await client.table('threads').delete().in_('account_id', account_ids).execute()
            
            # 3. 删除项目
            await client.table('projects').delete().in_('account_id', account_ids).execute()
            
            # 4. 删除账户用户关系
            await client.schema('basejump').from_('account_user').delete().eq('user_id', user_id).execute()
            
            # 5. 删除账户（只删除个人账户）
            await client.schema('basejump').from_('accounts').delete().in_('id', account_ids).eq('personal_account', True).execute()
        
        # 最后删除用户
        sync_client.auth.admin.delete_user(user_id)
        
        return True
        
    except Exception as e:
        logger.error(f"删除用户失败: {str(e)}")
        raise


def format_datetime(dt_str: str) -> str:
    """格式化日期时间字符串"""
    if not dt_str:
        return "从未"
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return dt_str


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    # 打印环境信息
    print(f"Supabase URL: {os.getenv('SUPABASE_URL')}")
    print(f"环境模式: {os.getenv('ENV_MODE', '未设置')}")
    print("-" * 80)
    
    try:
        if command == "list":
            # 列出所有用户
            users = await list_users()
            
            if not users:
                print("没有找到用户")
            else:
                print(f"找到 {len(users)} 个用户:\n")
                for i, user in enumerate(users):
                    print(f"{i+1}. {user['email']}")
                    print(f"   ID: {user['id']}")
                    print(f"   创建时间: {format_datetime(user['created_at'])}")
                    print(f"   最后登录: {format_datetime(user['last_sign_in_at'])}")
                    
                    if user['accounts']:
                        accounts = [f"{acc['accounts']['name']}({'个人' if acc['accounts']['personal_account'] else '团队'})" 
                                  for acc in user['accounts']]
                        print(f"   账户: {', '.join(accounts)}")
                    print()
        
        elif command == "create":
            if len(sys.argv) != 4:
                print("用法: python manage_users.py create <email> <password>")
                sys.exit(1)
            
            email = sys.argv[2]
            password = sys.argv[3]
            
            if "@" not in email:
                print("错误：请提供有效的邮箱地址")
                sys.exit(1)
            
            if len(password) < 6:
                print("错误：密码至少需要6个字符")
                sys.exit(1)
            
            user_info = await create_user(email, password)
            print(f"\n✅ 用户创建成功！")
            print(f"用户 ID: {user_info['user']['id']}")
            print(f"邮箱: {user_info['user']['email']}")
            print(f"\n登录凭据:")
            print(f"邮箱: {email}")
            print(f"密码: {password}")
        
        elif command == "delete":
            if len(sys.argv) != 3:
                print("用法: python manage_users.py delete <user_id>")
                sys.exit(1)
            
            user_id = sys.argv[2]
            
            # 先获取用户信息
            user_info = await get_user_details(user_id)
            if not user_info:
                print(f"错误：找不到用户 {user_id}")
                sys.exit(1)
            
            print(f"即将删除用户: {user_info['user']['email']} ({user_info['user']['id']})")
            print(f"这将同时删除:")
            print(f"- {len(user_info['accounts'])} 个账户")
            print(f"- {len(user_info['projects'])} 个项目")
            print(f"- {len(user_info['threads'])} 个对话")
            
            confirm = input("\n确认删除？(yes/no): ")
            if confirm.lower() == "yes":
                await delete_user(user_id)
                print("✅ 用户删除成功")
            else:
                print("取消删除")
        
        elif command == "info":
            if len(sys.argv) != 3:
                print("用法: python manage_users.py info <user_id_or_email>")
                sys.exit(1)
            
            user_identifier = sys.argv[2]
            user_info = await get_user_details(user_identifier)
            
            if not user_info:
                print(f"错误：找不到用户 {user_identifier}")
                sys.exit(1)
            
            user = user_info['user']
            print(f"\n用户信息:")
            print(f"ID: {user['id']}")
            print(f"邮箱: {user['email']}")
            print(f"邮箱已验证: {'是' if user['email_confirmed_at'] else '否'}")
            print(f"创建时间: {format_datetime(user['created_at'])}")
            print(f"最后登录: {format_datetime(user['last_sign_in_at'])}")
            
            if user_info['accounts']:
                print(f"\n账户 ({len(user_info['accounts'])} 个):")
                for acc in user_info['accounts']:
                    account = acc['accounts']
                    print(f"- {account['name'] or '未命名'} (ID: {account['id']})")
                    print(f"  类型: {'个人账户' if account['personal_account'] else '团队账户'}")
                    print(f"  角色: {acc['account_role']}")
            
            if user_info['projects']:
                print(f"\n项目 ({len(user_info['projects'])} 个):")
                for proj in user_info['projects']:
                    print(f"- {proj['name']} (ID: {proj['project_id']})")
            
            if user_info['threads']:
                print(f"\n对话 ({len(user_info['threads'])} 个):")
                for thread in user_info['threads'][:5]:  # 只显示前5个
                    print(f"- {thread['name'] or '未命名'} (ID: {thread['thread_id']})")
                if len(user_info['threads']) > 5:
                    print(f"  ... 还有 {len(user_info['threads']) - 5} 个对话")
        
        else:
            print(f"未知命令: {command}")
            print(__doc__)
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        sys.exit(1)
    finally:
        # 清理数据库连接
        await DBConnection.disconnect()


if __name__ == "__main__":
    asyncio.run(main())