# 快速测试脚本 - ComfyUI 连接

import httpx
import asyncio

async def test_comfyui():
    """测试 ComfyUI 是否正常运行"""
    url = "http://127.0.0.1:8188/system_stats"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                stats = response.json()
                print("✅ ComfyUI 连接成功!")
                print(f"系统信息: {stats}")
                return True
            else:
                print(f"❌ ComfyUI 响应异常: {response.status_code}")
                return False
                
    except httpx.ConnectError:
        print("❌ 无法连接到 ComfyUI")
        print("请确保:")
        print("  1. ComfyUI 已启动 (python main.py)")
        print("  2. 端口 8188 未被占用")
        print("  3. 防火墙允许本地连接")
        return False
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        return False

if __name__ == "__main__":
    print("测试 ComfyUI 连接...\n")
    result = asyncio.run(test_comfyui())
    
    if result:
        print("\n✅ 配置正确，可以开始使用!")
    else:
        print("\n❌ 配置有误，请检查上述问题")
