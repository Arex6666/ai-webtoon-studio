#!/usr/bin/env python3
"""
AI Webtoon Studio - 端到端 Demo 脚本

这个脚本演示完整的漫剧创作流程：
1. 创建项目和章节
2. 提交剧本并自动分镜
3. 查看生成的分镜和资产
4. 触发渲染任务
5. 获取渲染结果
6. 导出长条漫

使用方法:
    cd ai-webtoon-studio
    python scripts/demo_e2e.py

前提条件:
    - 后端服务运行中 (uvicorn app.main:app --reload --port 8000)
    - Docker 服务运行中 (postgres, redis, minio)
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Optional


API_BASE = "http://localhost:8000/api/v1"

# 示例剧本
SAMPLE_SCRIPT = """
场景：繁华的都市咖啡厅，阳光透过玻璃窗洒在木质桌椅上。

[旁白] 命运的邂逅，总是发生在最平凡的时刻。

李明（28岁，程序员）独自坐在窗边，专注地盯着笔记本电脑屏幕。他的咖啡已经凉了，但他浑然不觉。

突然，门口传来清脆的风铃声。

一个女孩走了进来——苏晴（25岁），一头及肩黑发，穿着白色连衣裙。她环顾四周，寻找空位。

苏晴的目光扫过咖啡厅，最后停在李明旁边的空座上。

苏晴微笑着走过来："请问，这里有人吗？"

李明抬起头，愣了一下。

李明："没...没有，请坐。"

苏晴坐下，从包里拿出一本《小王子》。

[旁白] 就这样，两条平行的人生轨迹，在这个普通的下午，开始交汇。

李明偷偷看了苏晴一眼，心跳突然加速。

苏晴似乎察觉到了什么，抬头看向窗外，嘴角微微上扬。
"""


class WebtoonStudioDemo:
    """Demo 客户端"""
    
    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.project_id: Optional[str] = None
        self.chapter_id: Optional[str] = None
    
    async def close(self):
        await self.client.aclose()
    
    async def check_health(self) -> bool:
        """检查 API 服务是否运行"""
        try:
            resp = await self.client.get(f"{self.base_url.replace('/api/v1', '')}/health")
            return resp.status_code == 200
        except Exception as e:
            print(f"❌ API 服务未运行: {e}")
            return False
    
    async def create_project(self, name: str, description: str = "") -> dict:
        """创建项目"""
        resp = await self.client.post(
            f"{self.base_url}/projects",
            json={"name": name, "description": description}
        )
        resp.raise_for_status()
        data = resp.json()
        self.project_id = data["id"]
        return data
    
    async def create_chapter(self, title: str, description: str = "") -> dict:
        """创建章节"""
        if not self.project_id:
            raise ValueError("请先创建项目")
        
        resp = await self.client.post(
            f"{self.base_url}/chapters",
            json={
                "project_id": self.project_id,
                "title": title,
                "description": description
            }
        )
        resp.raise_for_status()
        data = resp.json()
        self.chapter_id = data["id"]
        return data
    
    async def submit_script(self, script_text: str, style_hint: str = "korean_webtoon") -> dict:
        """提交剧本并自动分镜"""
        if not self.chapter_id:
            raise ValueError("请先创建章节")
        
        # 使用 query 参数传递文本
        params = {
            "script_text": script_text,
            "style_hint": style_hint,
            "auto_storyboard": "true"
        }
        
        resp = await self.client.put(
            f"{self.base_url}/chapters/{self.chapter_id}/script",
            params=params
        )
        resp.raise_for_status()
        return resp.json()
    
    async def get_studio_data(self) -> dict:
        """获取工作台数据"""
        if not self.chapter_id:
            raise ValueError("请先创建章节")
        
        resp = await self.client.get(f"{self.base_url}/chapters/{self.chapter_id}/studio")
        resp.raise_for_status()
        return resp.json()
    
    async def render_panel(self, panel_id: str, force: bool = False) -> dict:
        """渲染分镜"""
        resp = await self.client.post(
            f"{self.base_url}/render/panel",
            json={"panel_id": panel_id, "force_regenerate": force}
        )
        resp.raise_for_status()
        return resp.json()
    
    async def get_job_status(self, job_id: str) -> dict:
        """获取任务状态"""
        resp = await self.client.get(f"{self.base_url}/render/job/{job_id}")
        resp.raise_for_status()
        return resp.json()
    
    async def export_strip(self, include_typeset: bool = True) -> dict:
        """导出长条漫"""
        if not self.chapter_id:
            raise ValueError("请先创建章节")
        
        resp = await self.client.post(
            f"{self.base_url}/compose/strip",
            json={
                "chapter_id": self.chapter_id,
                "include_typeset": include_typeset
            }
        )
        resp.raise_for_status()
        return resp.json()
    
    async def get_download_url(self) -> dict:
        """获取下载链接"""
        if not self.chapter_id:
            raise ValueError("请先创建章节")
        
        resp = await self.client.get(f"{self.base_url}/compose/chapter/{self.chapter_id}/download")
        resp.raise_for_status()
        return resp.json()


async def run_demo():
    """运行 Demo"""
    print("=" * 60)
    print("🎬 AI Webtoon Studio - 端到端 Demo")
    print("=" * 60)
    print()
    
    demo = WebtoonStudioDemo()
    
    try:
        # 1. 检查服务
        print("📡 检查 API 服务...")
        if not await demo.check_health():
            print("❌ API 服务未运行，请先启动后端服务")
            print("   命令: cd apps/api && uvicorn app.main:app --reload --port 8000")
            return
        print("✅ API 服务运行正常\n")
        
        # 2. 创建项目
        print("📁 创建项目...")
        project = await demo.create_project(
            name=f"Demo 项目 - {datetime.now().strftime('%H:%M:%S')}",
            description="端到端 Demo 自动创建"
        )
        print(f"✅ 项目已创建: {project['name']} (ID: {project['id'][:8]}...)\n")
        
        # 3. 创建章节
        print("📖 创建章节...")
        chapter = await demo.create_chapter(
            title="第一章：咖啡厅的邂逅",
            description="男女主角的命运相遇"
        )
        print(f"✅ 章节已创建: {chapter['title']} (ID: {chapter['id'][:8]}...)\n")
        
        # 4. 提交剧本
        print("✍️ 提交剧本并自动分镜...")
        print("-" * 40)
        print("剧本内容（前 200 字）:")
        print(SAMPLE_SCRIPT[:200] + "...")
        print("-" * 40)
        
        result = await demo.submit_script(SAMPLE_SCRIPT, "korean_webtoon")
        print(f"\n✅ 分镜生成完成!")
        print(f"   - 创建了 {result['panels_created']} 个分镜")
        print(f"   - 检测到角色: {', '.join(result['characters_detected'])}")
        print(f"   - 检测到场景: {', '.join(result['scenes_detected'])}")
        
        if result.get('warnings'):
            print(f"   - ⚠️ 警告: {len(result['warnings'])} 个")
        print()
        
        # 5. 获取工作台数据
        print("📊 获取工作台数据...")
        studio = await demo.get_studio_data()
        
        print(f"✅ 工作台数据:")
        print(f"   - 分镜总数: {studio['stats']['total_panels']}")
        print(f"   - 已渲染: {studio['stats']['rendered_panels']}")
        print(f"   - 角色数: {len(studio['characters'])}")
        print(f"   - 场景数: {len(studio['scenes'])}")
        print()
        
        # 显示分镜列表
        print("📋 分镜列表:")
        for i, panel in enumerate(studio['panels'][:5]):  # 只显示前 5 个
            status_icon = {
                "draft": "📝",
                "rendering": "⏳",
                "rendered": "✅",
                "needs_fix": "⚠️"
            }.get(panel['render_status'], "❓")
            
            summary = panel.get('summary', panel.get('dialogue_preview', ''))[:40]
            print(f"   {status_icon} #{i+1}: {summary}...")
        
        if len(studio['panels']) > 5:
            print(f"   ... 还有 {len(studio['panels']) - 5} 个分镜")
        print()
        
        # 6. 渲染第一个分镜（Mock）
        if studio['panels']:
            print("🎨 渲染第一个分镜 (Mock)...")
            first_panel = studio['panels'][0]
            
            try:
                render_result = await demo.render_panel(first_panel['id'], force=True)
                print(f"   任务 ID: {render_result['job_id'][:8]}...")
                
                # 等待渲染完成
                print("   等待渲染完成...")
                for _ in range(10):  # 最多等待 10 秒
                    status = await demo.get_job_status(render_result['job_id'])
                    if status['status'] in ['completed', 'failed']:
                        break
                    await asyncio.sleep(1)
                    print(f"   进度: {status.get('progress', 0):.0f}%")
                
                if status['status'] == 'completed':
                    print("✅ 渲染完成!")
                else:
                    print(f"❌ 渲染状态: {status['status']}")
            except Exception as e:
                print(f"   ⚠️ 渲染请求失败 (可能是 Mock 模式): {e}")
        
        print()
        
        # 7. 导出（Mock）
        print("📦 导出长条漫 (Mock)...")
        try:
            export_result = await demo.export_strip()
            print(f"   导出任务 ID: {export_result['job_id'][:8]}...")
            print("   ⚠️ Mock 模式下实际不会生成文件")
        except Exception as e:
            print(f"   ⚠️ 导出请求失败: {e}")
        
        print()
        print("=" * 60)
        print("🎉 Demo 完成!")
        print("=" * 60)
        print()
        print("📱 前端工作台地址:")
        print(f"   http://localhost:3000/chapter/{demo.chapter_id}/studio")
        print()
        print("📚 API 文档地址:")
        print("   http://localhost:8000/docs")
        print()
        
    except httpx.HTTPStatusError as e:
        print(f"\n❌ API 错误: {e.response.status_code}")
        try:
            detail = e.response.json()
            print(f"   详情: {detail}")
        except:
            print(f"   响应: {e.response.text[:200]}")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
    finally:
        await demo.close()


if __name__ == "__main__":
    asyncio.run(run_demo())
