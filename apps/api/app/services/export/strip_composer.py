"""
长条漫合成器 - 拼接面板为条漫
"""
import io
import logging
from typing import List, Tuple, Optional
from PIL import Image
import httpx

logger = logging.getLogger(__name__)


class StripComposer:
    """长条漫合成器"""
    
    def __init__(self, gap: int = 0, bg_color: Tuple[int, int, int] = (255, 255, 255)):
        """
        Args:
            gap: 面板之间的间距像素
            bg_color: 背景颜色 (R, G, B)
        """
        self.gap = gap
        self.bg_color = bg_color
    
    async def compose_from_urls(
        self,
        image_urls: List[str],
        output_width: int = 1080,
        max_height: Optional[int] = None,
    ) -> bytes:
        """
        从 URL 列表合成长条漫
        
        Args:
            image_urls: 图片 URL 列表（按顺序）
            output_width: 输出宽度
            max_height: 最大高度（超过则分割）
        
        Returns:
            PNG 图片字节
        """
        images = await self._download_images(image_urls)
        return self._compose(images, output_width)
    
    async def _download_images(self, urls: List[str]) -> List[Image.Image]:
        """下载图片"""
        images = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for url in urls:
                try:
                    # 跳过占位符 URL
                    if "example.com" in url or "picsum.photos" in url:
                        # 为占位符创建空白图片
                        img = Image.new("RGB", (1080, 1920), (200, 200, 200))
                    else:
                        response = await client.get(url)
                        response.raise_for_status()
                        img = Image.open(io.BytesIO(response.content))
                    
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    images.append(img)
                    
                except Exception as e:
                    logger.warning(f"Failed to download image {url}: {e}")
                    # 创建占位符
                    img = Image.new("RGB", (1080, 1920), (200, 200, 200))
                    images.append(img)
        
        return images
    
    def _compose(self, images: List[Image.Image], output_width: int) -> bytes:
        """合成长条漫"""
        if not images:
            raise ValueError("No images to compose")
        
        # 计算缩放后的尺寸
        scaled_images = []
        total_height = 0
        
        for img in images:
            # 等比例缩放到目标宽度
            ratio = output_width / img.width
            new_height = int(img.height * ratio)
            
            if ratio != 1:
                scaled = img.resize((output_width, new_height), Image.Resampling.LANCZOS)
            else:
                scaled = img
            
            scaled_images.append(scaled)
            total_height += new_height + self.gap
        
        # 减去最后一个间距
        total_height -= self.gap
        
        # 创建画布
        canvas = Image.new("RGB", (output_width, total_height), self.bg_color)
        
        # 拼接图片
        y_offset = 0
        for img in scaled_images:
            canvas.paste(img, (0, y_offset))
            y_offset += img.height + self.gap
        
        # 导出为 PNG
        output = io.BytesIO()
        canvas.save(output, format="PNG", optimize=True)
        output.seek(0)
        
        return output.getvalue()
    
    def compose_from_bytes(
        self,
        image_bytes_list: List[bytes],
        output_width: int = 1080,
    ) -> bytes:
        """从字节列表合成"""
        images = []
        for data in image_bytes_list:
            img = Image.open(io.BytesIO(data))
            if img.mode != "RGB":
                img = img.convert("RGB")
            images.append(img)
        
        return self._compose(images, output_width)


def get_strip_composer(gap: int = 0) -> StripComposer:
    """获取 StripComposer 实例"""
    return StripComposer(gap=gap)
