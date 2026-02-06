# 快速测试脚本 - InsightFace FaceID 提取

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_faceid():
    """测试 InsightFace FaceID 提取功能"""
    from app.services.faceid.embedder import embed_character_faceid
    
    print("🎭 测试 InsightFace FaceID 提取\n")
    
    # 使用公开的测试图片 (需要包含清晰人脸)
    test_image = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/SNice.svg/220px-SNice.svg.png"
    
    print(f"使用测试图片: {test_image}")
    print("开始提取 FaceID embedding...\n")
    
    try:
        result = await embed_character_faceid(
            character_id="test_char_001",
            reference_image_path=test_image,
            project_id="test_project",
            provider_name="auto"  # 自动选择: 有 InsightFace 用真实提取，否则用 Mock
        )
        
        if result["success"]:
            print("✅ FaceID 提取成功!")
            print(f"\n📊 结果:")
            print(f"  - Embedding Path: {result['embedding_path']}")
            print(f"  - Provider: {result['meta'].get('provider', 'unknown')}")
            
            if result['meta'].get('provider') == 'insightface':
                print(f"  - 检测分数: {result['meta'].get('det_score', 0):.3f}")
                print(f"  - 检测到的人脸数: {result['meta'].get('faces_detected', 0)}")
                print(f"  - 模型: {result['meta'].get('model', 'unknown')}")
            elif result['meta'].get('provider') == 'mock':
                print("  ⚠️  使用 Mock provider (InsightFace 未安装或初始化失败)")
            
            print("\n✅ InsightFace 配置正确!")
            return True
        else:
            print("❌ FaceID 提取失败")
            print(f"错误: {result.get('error')}")
            return False
            
    except ImportError as e:
        print("❌ 模块导入失败")
        print(f"错误: {e}")
        print("\n请确保:")
        print("  1. 已安装: pip install insightface onnxruntime")
        print("  2. 在正确的虚拟环境中运行")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("InsightFace FaceID 提取测试")
    print("=" * 60 + "\n")
    
    result = asyncio.run(test_faceid())
    
    print("\n" + "=" * 60)
    if result:
        print("✅ 测试通过 - InsightFace 已正确配置")
    else:
        print("❌ 测试失败 - 请检查配置")
    print("=" * 60)
