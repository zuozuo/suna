#!/usr/bin/env python3
"""
Daytona 和 tmux 集成执行器
用于在 Daytona 开发环境中通过 tmux 执行 shell 脚本
"""

import subprocess
import time
import json
import os
from typing import Optional, List, Dict, Any


class DaytonaWorkspace:
    """Daytona 工作区管理器"""
    
    def __init__(self):
        self.workspace_name = None
        self.workspace_info = None
    
    def list_workspaces(self) -> List[Dict[str, Any]]:
        """列出所有 Daytona 工作区"""
        try:
            result = subprocess.run(
                ["daytona", "list", "--output", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"列出工作区失败: {e}")
            return []
    
    def create_workspace(self, name: str, git_url: str) -> bool:
        """创建新的 Daytona 工作区"""
        try:
            subprocess.run(
                ["daytona", "create", name, "--git-url", git_url],
                check=True
            )
            self.workspace_name = name
            return True
        except subprocess.CalledProcessError as e:
            print(f"创建工作区失败: {e}")
            return False
    
    def start_workspace(self, name: str) -> bool:
        """启动 Daytona 工作区"""
        try:
            subprocess.run(
                ["daytona", "start", name],
                check=True
            )
            self.workspace_name = name
            return True
        except subprocess.CalledProcessError as e:
            print(f"启动工作区失败: {e}")
            return False
    
    def stop_workspace(self, name: str) -> bool:
        """停止 Daytona 工作区"""
        try:
            subprocess.run(
                ["daytona", "stop", name],
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"停止工作区失败: {e}")
            return False
    
    def ssh_command(self, name: str, command: str) -> str:
        """在 Daytona 工作区中执行 SSH 命令"""
        try:
            result = subprocess.run(
                ["daytona", "ssh", name, "--", command],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"SSH 命令执行失败: {e}")
            return ""


class TmuxSession:
    """tmux 会话管理器"""
    
    def __init__(self, session_name: str = "daytona-session"):
        self.session_name = session_name
    
    def create_session(self) -> bool:
        """创建新的 tmux 会话"""
        try:
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", self.session_name],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            # 会话可能已存在
            return self.session_exists()
    
    def session_exists(self) -> bool:
        """检查 tmux 会话是否存在"""
        try:
            subprocess.run(
                ["tmux", "has-session", "-t", self.session_name],
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def send_command(self, command: str) -> None:
        """向 tmux 会话发送命令"""
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", self.session_name, command, "Enter"],
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"发送命令失败: {e}")
    
    def capture_output(self, start_line: int = -100) -> str:
        """捕获 tmux 窗格输出"""
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", self.session_name, "-p", "-S", str(start_line)],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"捕获输出失败: {e}")
            return ""
    
    def kill_session(self) -> None:
        """结束 tmux 会话"""
        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", self.session_name],
                check=True
            )
        except subprocess.CalledProcessError:
            pass
    
    def attach_session(self) -> None:
        """附加到 tmux 会话（交互式）"""
        try:
            subprocess.run(["tmux", "attach", "-t", self.session_name])
        except subprocess.CalledProcessError as e:
            print(f"附加会话失败: {e}")


class DaytonaTmuxExecutor:
    """Daytona 和 tmux 集成执行器"""
    
    def __init__(self, workspace_name: Optional[str] = None):
        self.daytona = DaytonaWorkspace()
        self.tmux = None
        self.workspace_name = workspace_name
    
    def setup_environment(self, workspace_name: str) -> bool:
        """设置执行环境"""
        # 启动 Daytona 工作区
        if not self.daytona.start_workspace(workspace_name):
            return False
        
        self.workspace_name = workspace_name
        
        # 创建 tmux 会话
        session_name = f"daytona-{workspace_name}"
        self.tmux = TmuxSession(session_name)
        
        if not self.tmux.create_session():
            print(f"无法创建 tmux 会话: {session_name}")
            return False
        
        return True
    
    def execute_script(self, script_path: str, wait_time: int = 2) -> str:
        """执行 shell 脚本并返回输出"""
        if not self.tmux:
            print("请先设置环境")
            return ""
        
        # 清空窗格
        self.tmux.send_command("clear")
        time.sleep(0.5)
        
        # 发送执行脚本的命令
        self.tmux.send_command(f"bash {script_path}")
        
        # 等待执行完成
        time.sleep(wait_time)
        
        # 捕获输出
        output = self.tmux.capture_output()
        
        return output
    
    def execute_in_daytona(self, command: str, use_tmux: bool = True) -> str:
        """在 Daytona 工作区中执行命令"""
        if not self.workspace_name:
            print("未设置工作区")
            return ""
        
        if use_tmux and self.tmux:
            # 通过 tmux 执行
            self.tmux.send_command(command)
            time.sleep(1)
            return self.tmux.capture_output(-50)
        else:
            # 直接通过 SSH 执行
            return self.daytona.ssh_command(self.workspace_name, command)
    
    def execute_script_with_monitoring(self, script_path: str, 
                                     check_interval: float = 0.5,
                                     timeout: float = 30) -> Dict[str, Any]:
        """执行脚本并实时监控输出"""
        if not self.tmux:
            print("请先设置环境")
            return {"success": False, "output": "", "error": "未设置环境"}
        
        # 记录开始时间
        start_time = time.time()
        
        # 清空窗格并执行脚本
        self.tmux.send_command("clear")
        time.sleep(0.2)
        self.tmux.send_command(f"bash {script_path}; echo '===SCRIPT_DONE==='")
        
        # 监控输出
        output_lines = []
        last_output = ""
        
        while time.time() - start_time < timeout:
            current_output = self.tmux.capture_output()
            
            # 检查是否完成
            if "===SCRIPT_DONE===" in current_output:
                # 移除标记
                current_output = current_output.replace("===SCRIPT_DONE===", "").strip()
                return {
                    "success": True,
                    "output": current_output,
                    "execution_time": time.time() - start_time
                }
            
            # 检查新输出
            if current_output != last_output:
                new_lines = current_output[len(last_output):].strip()
                if new_lines:
                    print(f"[新输出] {new_lines}")
                    output_lines.append(new_lines)
                last_output = current_output
            
            time.sleep(check_interval)
        
        return {
            "success": False,
            "output": last_output,
            "error": "执行超时",
            "execution_time": timeout
        }
    
    def cleanup(self):
        """清理资源"""
        if self.tmux:
            self.tmux.kill_session()
        
        if self.workspace_name:
            self.daytona.stop_workspace(self.workspace_name)


# 使用示例
if __name__ == "__main__":
    # 创建执行器实例
    executor = DaytonaTmuxExecutor()
    
    # 示例1: 在现有工作区中执行命令
    print("=== 示例1: 执行简单命令 ===")
    if executor.setup_environment("my-workspace"):
        # 执行命令
        output = executor.execute_in_daytona("ls -la")
        print(f"命令输出:\n{output}")
        
        # 执行脚本
        script_content = """
        echo "开始执行脚本..."
        date
        echo "当前目录: $(pwd)"
        echo "系统信息: $(uname -a)"
        echo "脚本执行完成!"
        """
        
        # 创建临时脚本
        with open("/tmp/test_script.sh", "w") as f:
            f.write(script_content)
        
        # 复制脚本到工作区
        executor.execute_in_daytona("cat > /tmp/test_script.sh << 'EOF'\n" + script_content + "\nEOF")
        
        # 执行脚本
        print("\n=== 示例2: 执行脚本 ===")
        result = executor.execute_script("/tmp/test_script.sh", wait_time=3)
        print(f"脚本输出:\n{result}")
        
        # 执行带监控的脚本
        print("\n=== 示例3: 执行脚本并监控 ===")
        long_script = """
        for i in {1..5}; do
            echo "处理步骤 $i..."
            sleep 1
        done
        echo "所有步骤完成!"
        """
        
        executor.execute_in_daytona("cat > /tmp/long_script.sh << 'EOF'\n" + long_script + "\nEOF")
        
        result = executor.execute_script_with_monitoring("/tmp/long_script.sh")
        print(f"\n执行结果: {result}")
        
        # 清理
        executor.cleanup()
    
    # 示例4: 创建新工作区并执行
    print("\n=== 示例4: 创建新工作区 ===")
    daytona = DaytonaWorkspace()
    
    # 列出现有工作区
    workspaces = daytona.list_workspaces()
    print(f"现有工作区: {[w.get('name') for w in workspaces]}")
    
    # 创建新工作区（需要提供实际的 Git URL）
    # if daytona.create_workspace("test-workspace", "https://github.com/user/repo.git"):
    #     executor2 = DaytonaTmuxExecutor()
    #     if executor2.setup_environment("test-workspace"):
    #         output = executor2.execute_in_daytona("git status")
    #         print(f"Git 状态:\n{output}")
    #         executor2.cleanup()