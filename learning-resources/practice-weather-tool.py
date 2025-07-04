"""
实践项目：创建天气查询工具
这是一个学习示例，展示如何为 Suna 创建自定义工具

学习目标：
1. 理解工具接口设计
2. 实现 API 调用
3. 处理错误和边界情况
4. 集成到 Agent 系统
"""

import os
import httpx
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# 模拟的工具基类（实际项目中从 sandbox.tool_base 导入）
class ToolBase:
    """工具基类接口"""
    name: str
    description: str
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

class WeatherToolInput(BaseModel):
    """天气工具的输入参数模型"""
    city: str = Field(..., description="要查询天气的城市名称")
    country_code: Optional[str] = Field(None, description="国家代码，如 CN、US")
    units: str = Field("metric", description="温度单位：metric（摄氏度）或 imperial（华氏度）")

class WeatherTool(ToolBase):
    """
    天气查询工具实现
    
    这个工具演示了：
    1. 如何定义工具参数
    2. 如何调用外部 API
    3. 如何处理错误
    4. 如何格式化返回结果
    """
    
    def __init__(self):
        self.name = "weather_query"
        self.description = "查询指定城市的当前天气信息"
        # 实际使用时需要真实的 API key
        self.api_key = os.getenv("OPENWEATHER_API_KEY", "demo_key")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
    
    async def execute(self, city: str, country_code: Optional[str] = None, 
                     units: str = "metric") -> Dict[str, Any]:
        """
        执行天气查询
        
        Args:
            city: 城市名称
            country_code: 可选的国家代码
            units: 温度单位
            
        Returns:
            包含天气信息的字典
        """
        try:
            # 构建查询参数
            location = f"{city},{country_code}" if country_code else city
            params = {
                "q": location,
                "appid": self.api_key,
                "units": units,
                "lang": "zh_cn"  # 返回中文描述
            }
            
            # 发送 API 请求
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                
            data = response.json()
            
            # 格式化返回数据
            weather_info = {
                "location": {
                    "city": data["name"],
                    "country": data["sys"]["country"],
                    "coordinates": {
                        "lat": data["coord"]["lat"],
                        "lon": data["coord"]["lon"]
                    }
                },
                "current": {
                    "temperature": data["main"]["temp"],
                    "feels_like": data["main"]["feels_like"],
                    "humidity": data["main"]["humidity"],
                    "pressure": data["main"]["pressure"],
                    "description": data["weather"][0]["description"],
                    "icon": data["weather"][0]["icon"]
                },
                "wind": {
                    "speed": data["wind"]["speed"],
                    "direction": data["wind"].get("deg", 0)
                },
                "units": {
                    "temperature": "°C" if units == "metric" else "°F",
                    "wind_speed": "m/s" if units == "metric" else "mph"
                }
            }
            
            return {
                "success": True,
                "data": weather_info,
                "message": f"成功获取 {city} 的天气信息"
            }
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "success": False,
                    "error": f"未找到城市：{city}",
                    "error_type": "city_not_found"
                }
            else:
                return {
                    "success": False,
                    "error": f"API 请求失败：{e.response.status_code}",
                    "error_type": "api_error"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"查询天气时发生错误：{str(e)}",
                "error_type": "unknown_error"
            }
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """
        返回工具定义，用于 Agent 系统注册
        
        这个定义告诉 Agent：
        1. 工具的名称和描述
        2. 需要哪些参数
        3. 参数的类型和说明
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "要查询天气的城市名称"
                    },
                    "country_code": {
                        "type": "string",
                        "description": "可选的国家代码（如 CN、US）",
                        "optional": True
                    },
                    "units": {
                        "type": "string",
                        "description": "温度单位：metric（摄氏度）或 imperial（华氏度）",
                        "enum": ["metric", "imperial"],
                        "default": "metric"
                    }
                },
                "required": ["city"]
            }
        }
    
    async def format_for_display(self, result: Dict[str, Any]) -> str:
        """
        将结果格式化为用户友好的显示格式
        
        Args:
            result: execute 方法返回的结果
            
        Returns:
            格式化的字符串
        """
        if not result["success"]:
            return f"❌ {result['error']}"
        
        data = result["data"]
        location = data["location"]
        current = data["current"]
        wind = data["wind"]
        units = data["units"]
        
        return f"""
🌍 **{location['city']}, {location['country']}**
📍 坐标：{location['coordinates']['lat']}, {location['coordinates']['lon']}

🌡️ **当前天气**
- 温度：{current['temperature']}{units['temperature']}
- 体感：{current['feels_like']}{units['temperature']}
- 描述：{current['description']}
- 湿度：{current['humidity']}%
- 气压：{current['pressure']} hPa

💨 **风况**
- 风速：{wind['speed']} {units['wind_speed']}
- 风向：{wind['direction']}°
"""

# 测试代码
async def test_weather_tool():
    """测试天气工具的功能"""
    tool = WeatherTool()
    
    # 测试正常查询
    print("测试 1：查询北京天气")
    result = await tool.execute(city="Beijing", country_code="CN")
    formatted = await tool.format_for_display(result)
    print(formatted)
    
    # 测试错误处理
    print("\n测试 2：查询不存在的城市")
    result = await tool.execute(city="NotExistCity123")
    formatted = await tool.format_for_display(result)
    print(formatted)
    
    # 测试不同单位
    print("\n测试 3：使用华氏度查询")
    result = await tool.execute(city="New York", country_code="US", units="imperial")
    formatted = await tool.format_for_display(result)
    print(formatted)

if __name__ == "__main__":
    import asyncio
    
    # 设置演示用的 API key（实际使用需要真实的 key）
    os.environ["OPENWEATHER_API_KEY"] = "demo_key"
    
    print("=== Suna 天气工具学习示例 ===\n")
    print("注意：这是一个学习示例，实际运行需要：")
    print("1. 获取 OpenWeatherMap API key")
    print("2. 设置环境变量 OPENWEATHER_API_KEY")
    print("3. 将工具集成到 Suna 的工具系统中")
    print("\n" + "="*40 + "\n")
    
    # 运行测试
    # asyncio.run(test_weather_tool())
    
    # 显示工具定义
    tool = WeatherTool()
    import json
    print("工具定义：")
    print(json.dumps(tool.get_tool_definition(), indent=2, ensure_ascii=False))