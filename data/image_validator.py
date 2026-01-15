"""图片校验器模块"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from PIL import Image
except ImportError:
    Image = None

logger = logging.getLogger(__name__)


class ImageFormat(str, Enum):
    """支持的图片格式"""
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    BMP = "bmp"
    WEBP = "webp"


# 支持的扩展名集合
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# 图片限制常量
MAX_IMAGE_COUNT = 9          # 朋友圈最大图片数
MAX_IMAGE_SIZE_MB = 10       # 单张图片最大大小 (MB)
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
MIN_IMAGE_DIMENSION = 200    # 最小尺寸 (像素)


@dataclass
class ValidationError:
    """校验错误"""
    path: str
    error_type: str
    message: str


@dataclass
class ValidationResult:
    """校验结果"""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[str]
    valid_paths: List[str]

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class ImageValidator:
    """图片校验器"""

    def __init__(
        self,
        max_count: int = MAX_IMAGE_COUNT,
        max_size_bytes: int = MAX_IMAGE_SIZE_BYTES,
        min_dimension: int = MIN_IMAGE_DIMENSION,
    ):
        self.max_count = max_count
        self.max_size_bytes = max_size_bytes
        self.min_dimension = min_dimension

    def validate_single(self, image_path: str) -> Tuple[bool, Optional[str]]:
        """校验单张图片"""
        path = Path(image_path)

        # 检查文件存在
        if not path.exists():
            return False, f"文件不存在: {image_path}"

        if not path.is_file():
            return False, f"不是有效文件: {image_path}"

        # 检查扩展名
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return False, f"不支持的格式 {ext}，支持: {', '.join(SUPPORTED_EXTENSIONS)}"

        # 检查文件大小
        file_size = path.stat().st_size
        if file_size > self.max_size_bytes:
            size_mb = file_size / (1024 * 1024)
            return False, f"文件过大: {size_mb:.1f}MB，最大允许 {MAX_IMAGE_SIZE_MB}MB"

        if file_size == 0:
            return False, "文件大小为0"

        # 检查图片尺寸 (需要 Pillow)
        if Image is not None:
            try:
                with Image.open(path) as img:
                    width, height = img.size
                    if width < self.min_dimension or height < self.min_dimension:
                        return False, f"尺寸过小: {width}x{height}，最小要求 {self.min_dimension}x{self.min_dimension}"
            except Exception as e:
                return False, f"无法读取图片: {e}"

        return True, None

    def validate_batch(self, image_paths: List[str]) -> ValidationResult:
        """批量校验图片"""
        errors: List[ValidationError] = []
        warnings: List[str] = []
        valid_paths: List[str] = []

        # 检查数量限制
        if len(image_paths) > self.max_count:
            warnings.append(
                f"图片数量 {len(image_paths)} 超过限制 {self.max_count}，将只处理前 {self.max_count} 张"
            )
            image_paths = image_paths[:self.max_count]

        # 逐张校验
        for path in image_paths:
            is_valid, error_msg = self.validate_single(path)
            if is_valid:
                valid_paths.append(path)
            else:
                errors.append(ValidationError(
                    path=path,
                    error_type=self._classify_error(error_msg),
                    message=error_msg or "未知错误",
                ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            valid_paths=valid_paths,
        )

    def _classify_error(self, error_msg: Optional[str]) -> str:
        """分类错误类型"""
        if not error_msg:
            return "unknown"

        msg_lower = error_msg.lower()
        if "不存在" in error_msg or "not exist" in msg_lower:
            return "not_found"
        if "格式" in error_msg or "format" in msg_lower:
            return "invalid_format"
        if "过大" in error_msg or "size" in msg_lower:
            return "file_too_large"
        if "尺寸" in error_msg or "dimension" in msg_lower:
            return "dimension_too_small"
        if "读取" in error_msg or "read" in msg_lower:
            return "read_error"

        return "unknown"

    def check_format(self, image_path: str) -> Optional[str]:
        """检查图片格式，返回规范化的格式名"""
        path = Path(image_path)
        ext = path.suffix.lower().lstrip(".")

        if ext in ("jpg", "jpeg"):
            return "JPEG"
        elif ext == "png":
            return "PNG"
        elif ext == "gif":
            return "GIF"
        elif ext == "bmp":
            return "BMP"
        elif ext == "webp":
            return "WEBP"

        return None

    def get_image_info(self, image_path: str) -> Optional[dict]:
        """获取图片信息"""
        path = Path(image_path)

        if not path.exists():
            return None

        info = {
            "path": str(path),
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "size_mb": path.stat().st_size / (1024 * 1024),
        }

        if Image is not None:
            try:
                with Image.open(path) as img:
                    info["width"] = img.size[0]
                    info["height"] = img.size[1]
                    info["format"] = img.format
                    info["mode"] = img.mode
                    info["is_animated"] = getattr(img, "is_animated", False)
            except Exception as e:
                logger.warning(f"无法读取图片信息: {path}, {e}")

        return info

    def needs_compression(self, image_path: str) -> bool:
        """判断是否需要压缩"""
        path = Path(image_path)
        if not path.exists():
            return False
        return path.stat().st_size > self.max_size_bytes


def validate_images(image_paths: List[str]) -> ValidationResult:
    """便捷函数：校验图片列表"""
    validator = ImageValidator()
    return validator.validate_batch(image_paths)


def is_valid_image(image_path: str) -> bool:
    """便捷函数：检查单张图片是否有效"""
    validator = ImageValidator()
    is_valid, _ = validator.validate_single(image_path)
    return is_valid
