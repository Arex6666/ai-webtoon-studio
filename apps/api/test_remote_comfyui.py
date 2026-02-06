# 远程 ComfyUI 连接测试脚本

import httpx
import asyncio
import sys
import os

def print_info(msg):
    print(f"ℹ️  {msg}")

def print_success(msg):
    print(f"✅ {msg}")

def print_error(msg):
    print(f"❌ {msg}")

def print_warning(msg):
    print(f"⚠️  {msg}")

async def test_remote_comfyui(url: str):
    """测试远程 ComfyUI 连接"""
    print("\n" + "="*60)
    print("远程 ComfyUI 连接测试")
    print("="*60 + "\n")
    
    print_info(f"测试 URL: {url}")
    
    # 测试 1: 基本连接
    print("\n1️⃣  测试基本连接...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{url}/system_stats")
            
            if response.status_code == 200:
                print_success("连接成功!")
                stats = response.json()
                
                # 显示系统信息
                if isinstance(stats, dict):
                    system = stats.get('system', {})
                    print(f"    OS: {system.get('os', 'Unknown')}")
                    
                    ram_used = system.get('ram_used', 0)
                    ram_total = system.get('ram_total', 0)
                    if ram_total > 0:
                        print(f"    RAM: {ram_used}MB / {ram_total}MB ({ram_used/ram_total*100:.1f}%)")
                
                return True
            else:
                print_error(f"HTTP {response.status_code}: {response.text[:100]}")
                return False
                
    except httpx.ConnectError as e:
        print_error("连接失败 - 无法连接到服务器")
        print("\n📋 排查建议:")
        print("  1. 检查服务器 IP 地址是否正确")
        print("  2. 确认 ComfyUI 使用 --listen 0.0.0.0 启动")
        print(f"     服务器命令: python main.py --listen 0.0.0.0 --port 8188")
        print("  3. 检查防火墙是否允许 8188 端口")
        print("  4. 如果是云服务器，检查安全组配置")
        return False
        
    except httpx.TimeoutException:
        print_error("连接超时 - 网络可能不通")
        print("\n📋 排查建议:")
        print("  1. 检查网络连接")
        print("  2. 尝试 ping 服务器 IP")
        print(f"     ping {url.split('://')[1].split(':')[0]}")
        return False
        
    except Exception as e:
        print_error(f"未知错误: {e}")
        return False

def get_comfyui_url():
    """从 .env 或用户输入获取 URL"""
    # 尝试从 .env 读取
    try:
        from dotenv import load_dotenv
        load_dotenv()
        url = os.getenv("COMFYUI_URL")
        if url:
            print_info(f"从 .env 读取到 URL: {url}")
            return url
    except:
        pass
    
    # 从命令行参数
    if len(sys.argv) > 1:
        return sys.argv[1]
    
    # 提示用户输入
    print("\n请输入远程 ComfyUI 服务器地址:")
    print("示例: http://192.168.1.100:8188")
    url = input("URL: ").strip()
    
    if not url:
        print_error("URL 不能为空")
        sys.exit(1)
    
    # 添加 http:// 前缀
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    
    return url

async def main():
    url = get_comfyui_url()
    
    result = await test_remote_comfyui(url)
    
    print("\n" + "="*60)
    if result:
        print_success("✅ 远程 ComfyUI 配置正确!\n")
        print("下一步:")
        print("  1. 确保 .env 中 COMFYUI_URL 配置正确")
        print("  2. 启动后端 API: uvicorn app.main:app --reload")
        print("  3. 测试端到端渲染")
    else:
        print_error("❌ 远程 ComfyUI 连接失败\n")
        print("请按照上述建议排查问题")
        print("或查看完整指南: REMOTE_COMFYUI_GUIDE.md")
    print("="*60 + "\n")
    
    sys.exit(0 if result else 1)

if __name__ == "__main__":
    asyncio.run(main())
