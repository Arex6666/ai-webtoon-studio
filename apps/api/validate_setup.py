# 一键验证脚本 - 检查所有配置

import asyncio
import httpx
import sys
import os

# ANSI 颜色代码
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text.center(60)}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

async def check_comfyui():
    """检查 ComfyUI 连接"""
    print(f"\n{BLUE}1. 检查 ComfyUI 连接...{RESET}")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://127.0.0.1:8188/system_stats")
            if response.status_code == 200:
                print_success("ComfyUI 运行正常")
                return True
            else:
                print_error(f"ComfyUI 响应异常: {response.status_code}")
                return False
    except:
        print_error("ComfyUI 未运行")
        print_warning("启动 ComfyUI: cd D:\\ComfyUI\\ComfyUI && python main.py")
        return False

def check_insightface():
    """检查 InsightFace 安装"""
    print(f"\n{BLUE}2. 检查 InsightFace 安装...{RESET}")
    
    try:
        import insightface
        print_success(f"InsightFace 已安装 (版本: {insightface.__version__})")
        return True
    except ImportError:
        print_error("InsightFace 未安装")
        print_warning("安装命令: pip install insightface onnxruntime")
        return False

def check_env_file():
    """检查 .env 文件"""
    print(f"\n{BLUE}3. 检查 .env 配置...{RESET}")
    
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    if not os.path.exists(env_path):
        print_error(".env 文件不存在")
        print_warning("创建 .env 文件并添加 COMFYUI_URL=http://127.0.0.1:8188")
        return False
    
    with open(env_path, 'r') as f:
        content = f.read()
        if 'COMFYUI_URL' in content:
            print_success(".env 文件配置正确")
            return True
        else:
            print_error(".env 缺少 COMFYUI_URL 配置")
            return False

async def check_api_health():
    """检查 API 健康状态"""
    print(f"\n{BLUE}4. 检查后端 API...{RESET}")
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get("http://localhost:8000/")
            if response.status_code == 200:
                print_success("后端 API 运行正常")
                return True
            else:
                print_error(f"API 响应异常: {response.status_code}")
                return False
    except:
        print_error("后端 API 未运行")
        print_warning("启动命令: uvicorn app.main:app --reload")
        return False

def check_models():
    """检查模型文件"""
    print(f"\n{BLUE}5. 检查 ComfyUI 模型...{RESET}")
    
    model_paths = [
        "D:/ComfyUI/ComfyUI/models/checkpoints",
        "C:/ComfyUI/models/checkpoints"
    ]
    
    for path in model_paths:
        if os.path.exists(path):
            files = [f for f in os.listdir(path) if f.endswith('.safetensors')]
            if files:
                print_success(f"找到 {len(files)} 个模型文件")
                for f in files:
                    print(f"  - {f}")
                return True
    
    print_error("未找到模型文件")
    print_warning("请下载 FLUX 或 SDXL 模型到 models/checkpoints/")
    return False

async def main():
    print_header("AI Webtoon Studio - 配置验证")
    
    results = []
    
    # 运行所有检查
    results.append(("ComfyUI", await check_comfyui()))
    results.append(("InsightFace", check_insightface()))
    results.append((".env配置", check_env_file()))
    results.append(("后端API", await check_api_health()))
    results.append(("模型文件", check_models()))
    
    # 汇总结果
    print_header("验证结果汇总")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        if result:
            print_success(f"{name}: 通过")
        else:
            print_error(f"{name}: 失败")
    
    print(f"\n{BLUE}总计: {passed}/{total} 通过{RESET}\n")
    
    if passed == total:
        print_success("🎉 所有配置检查通过！可以开始端到端验证")
        print(f"\n{BLUE}下一步:{RESET}")
        print("  1. 访问 http://localhost:3001")
        print("  2. 创建项目并输入剧本")
        print("  3. 生成分镜 → 上传角色参考图 → 渲染 → 导出")
    else:
        print_error("部分配置未通过，请按照上述提示修复")
        print(f"\n{BLUE}完整配置指南:{RESET}")
        print("  查看 SETUP_GUIDE.md 获取详细步骤")

if __name__ == "__main__":
    asyncio.run(main())
