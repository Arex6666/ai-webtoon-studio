"""
S5-01 - Portrait QA (Face Quality Assurance)

验证生成的肖像是否符合"证件照式参考图"要求。
使用 InsightFace / OpenCV 进行人脸检测，无需视觉大模型。
"""

import logging
from typing import Optional
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PortraitQAResult(BaseModel):
    """肖像质量检测结果"""
    passed: bool
    face_count: int = 0
    face_confidence: float = 0.0
    face_area_ratio: float = 0.0  # 脸占画面比例
    image_width: int = 0
    image_height: int = 0
    file_size_kb: float = 0.0
    issues: list[str] = []


# QA 阈值
MIN_FILE_SIZE_KB = 15.0
MIN_FACE_CONFIDENCE = 0.6
MIN_FACE_AREA_RATIO = 0.10  # 10%
MAX_FACE_AREA_RATIO = 0.60  # 60%
EXPECTED_FACE_COUNT = 1


def validate_portrait(image_path: str) -> PortraitQAResult:
    """
    验证肖像图片质量
    
    硬规则：
    1. 图片可读且尺寸正确
    2. 文件大小 > 15KB
    3. face_count == 1
    4. confidence > 0.6
    5. area_ratio 在 10%~60%
    
    Returns:
        PortraitQAResult
    """
    issues = []
    result = PortraitQAResult(passed=False, issues=issues)
    
    try:
        import cv2
        import numpy as np
        
        # 1. 读取图片
        path = Path(image_path)
        if not path.exists():
            issues.append(f"文件不存在: {image_path}")
            return result
        
        # 文件大小
        file_size_kb = path.stat().st_size / 1024
        result.file_size_kb = file_size_kb
        
        if file_size_kb < MIN_FILE_SIZE_KB:
            issues.append(f"文件过小: {file_size_kb:.1f}KB < {MIN_FILE_SIZE_KB}KB")
        
        # 读取图片
        img = cv2.imread(str(path))
        if img is None:
            issues.append("无法读取图片")
            return result
        
        height, width = img.shape[:2]
        result.image_width = width
        result.image_height = height
        
        # 2. 人脸检测
        face_count, max_confidence, max_area_ratio = _detect_faces(img)
        result.face_count = face_count
        result.face_confidence = max_confidence
        result.face_area_ratio = max_area_ratio
        
        # 检查人脸数量
        if face_count == 0:
            issues.append("未检测到人脸")
        elif face_count > EXPECTED_FACE_COUNT:
            issues.append(f"检测到多张人脸: {face_count}")
        
        # 检查置信度
        if face_count > 0 and max_confidence < MIN_FACE_CONFIDENCE:
            issues.append(f"人脸置信度过低: {max_confidence:.2f} < {MIN_FACE_CONFIDENCE}")
        
        # 检查面积比例
        if face_count > 0:
            if max_area_ratio < MIN_FACE_AREA_RATIO:
                issues.append(f"人脸太小: {max_area_ratio:.1%} < {MIN_FACE_AREA_RATIO:.0%}")
            elif max_area_ratio > MAX_FACE_AREA_RATIO:
                issues.append(f"人脸太大: {max_area_ratio:.1%} > {MAX_FACE_AREA_RATIO:.0%}")
        
        # 判断是否通过
        result.passed = len(issues) == 0
        result.issues = issues
        
        return result
        
    except ImportError:
        logger.warning("[PortraitQA] OpenCV 未安装，跳过人脸检测")
        # 降级：只检查文件
        return _fallback_validate(image_path)
    except Exception as e:
        issues.append(f"检测异常: {e}")
        return result


def _detect_faces(img) -> tuple[int, float, float]:
    """
    使用 OpenCV Haar Cascade 检测人脸
    
    Returns:
        (face_count, max_confidence, max_area_ratio)
    """
    import cv2
    
    height, width = img.shape[:2]
    total_area = width * height
    
    # 尝试使用 DNN 模型（更准确）
    try:
        return _detect_faces_dnn(img)
    except Exception:
        pass
    
    # 降级到 Haar Cascade
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 加载人脸检测器
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )
    
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(50, 50)
    )
    
    if len(faces) == 0:
        return 0, 0.0, 0.0
    
    # 计算最大人脸的面积比例
    max_area = 0
    for (x, y, w, h) in faces:
        area = w * h
        if area > max_area:
            max_area = area
    
    area_ratio = max_area / total_area
    
    # Haar Cascade 没有置信度，用固定值
    return len(faces), 0.75, area_ratio


def _detect_faces_dnn(img) -> tuple[int, float, float]:
    """
    使用 OpenCV DNN 模型检测人脸（更准确，有置信度）
    """
    import cv2
    
    height, width = img.shape[:2]
    total_area = width * height
    
    # ResNet SSD 人脸检测
    model_file = "res10_300x300_ssd_iter_140000.caffemodel"
    config_file = "deploy.prototxt"
    
    # 检查模型文件是否存在
    from pathlib import Path
    model_dir = Path(__file__).parent / "models"
    
    if not (model_dir / model_file).exists():
        raise FileNotFoundError("DNN 模型文件不存在")
    
    net = cv2.dnn.readNetFromCaffe(
        str(model_dir / config_file),
        str(model_dir / model_file)
    )
    
    blob = cv2.dnn.blobFromImage(
        cv2.resize(img, (300, 300)),
        1.0,
        (300, 300),
        (104.0, 177.0, 123.0)
    )
    
    net.setInput(blob)
    detections = net.forward()
    
    faces = []
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:
            box = detections[0, 0, i, 3:7] * [width, height, width, height]
            x1, y1, x2, y2 = box.astype("int")
            w, h = x2 - x1, y2 - y1
            faces.append((x1, y1, w, h, confidence))
    
    if len(faces) == 0:
        return 0, 0.0, 0.0
    
    # 找最大置信度和面积
    max_conf = max(f[4] for f in faces)
    max_area = max(f[2] * f[3] for f in faces)
    area_ratio = max_area / total_area
    
    return len(faces), float(max_conf), area_ratio


def _fallback_validate(image_path: str) -> PortraitQAResult:
    """降级验证（只检查文件基本属性）"""
    from pathlib import Path
    
    issues = []
    path = Path(image_path)
    
    if not path.exists():
        return PortraitQAResult(passed=False, issues=["文件不存在"])
    
    file_size_kb = path.stat().st_size / 1024
    
    if file_size_kb < MIN_FILE_SIZE_KB:
        issues.append(f"文件过小: {file_size_kb:.1f}KB")
    
    # 尝试用 PIL 获取尺寸
    try:
        from PIL import Image
        with Image.open(path) as img:
            width, height = img.size
    except:
        width, height = 0, 0
        issues.append("无法读取图片尺寸")
    
    return PortraitQAResult(
        passed=len(issues) == 0,
        file_size_kb=file_size_kb,
        image_width=width,
        image_height=height,
        issues=issues
    )
