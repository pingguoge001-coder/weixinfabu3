"""图片加载器模块"""

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image
except ImportError:
    Image = None

from .image_validator import ImageValidator, ValidationResult, MAX_IMAGE_SIZE_BYTES
from .path_mapper import PathMapper, get_path_mapper

logger = logging.getLogger(__name__)

# 压缩配置
COMPRESSION_QUALITY_START = 95
COMPRESSION_QUALITY_MIN = 60
COMPRESSION_QUALITY_STEP = 5

# 缓存元数据文件名
CACHE_META_FILE = ".image_cache_meta.json"


@dataclass
class LoadResult:
    """加载结果"""
    success: bool
    source_path: str
    cached_path: Optional[str] = None
    error: Optional[str] = None
    was_compressed: bool = False
    was_gif_extracted: bool = False
    md5: Optional[str] = None
    original_size: int = 0
    final_size: int = 0


@dataclass
class BatchLoadResult:
    """批量加载结果"""
    results: List[LoadResult] = field(default_factory=list)
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0  # 使用缓存的数量

    @property
    def all_success(self) -> bool:
        return self.failed_count == 0

    @property
    def cached_paths(self) -> List[str]:
        """获取所有成功加载的缓存路径"""
        return [r.cached_path for r in self.results if r.success and r.cached_path]


class ImageLoader:
    """图片加载器"""

    def __init__(
        self,
        path_mapper: Optional[PathMapper] = None,
        validator: Optional[ImageValidator] = None,
        cache_dir: Optional[Path] = None,
    ):
        self.path_mapper = path_mapper or get_path_mapper()
        self.validator = validator or ImageValidator()

        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = self.path_mapper.cache_dir

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_meta: Dict[str, dict] = {}
        self._load_cache_meta()

    def _load_cache_meta(self) -> None:
        """加载缓存元数据"""
        meta_file = self.cache_dir / CACHE_META_FILE
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    self._cache_meta = json.load(f)
            except Exception as e:
                logger.warning(f"加载缓存元数据失败: {e}")
                self._cache_meta = {}

    def _save_cache_meta(self) -> None:
        """保存缓存元数据"""
        meta_file = self.cache_dir / CACHE_META_FILE
        try:
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(self._cache_meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存缓存元数据失败: {e}")

    def calculate_md5(self, file_path: Path) -> str:
        """计算文件 MD5"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def get_cached_path(self, md5: str, extension: str) -> Path:
        """根据 MD5 获取缓存路径"""
        # 使用 MD5 前两位作为子目录，避免单目录文件过多
        subdir = md5[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(parents=True, exist_ok=True)
        return cache_subdir / f"{md5}{extension}"

    def is_cached(self, source_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        检查文件是否已缓存

        Returns:
            (是否缓存, 缓存路径, MD5)
        """
        source = Path(source_path)
        if not source.exists():
            return False, None, None

        md5 = self.calculate_md5(source)

        if md5 in self._cache_meta:
            cached_path = self._cache_meta[md5].get("cached_path")
            if cached_path and Path(cached_path).exists():
                return True, cached_path, md5

        return False, None, md5

    def compress_image(
        self,
        source_path: Path,
        target_path: Path,
        max_size: int = MAX_IMAGE_SIZE_BYTES,
    ) -> Tuple[bool, Optional[str]]:
        """
        压缩图片

        Args:
            source_path: 源文件路径
            target_path: 目标文件路径
            max_size: 最大文件大小

        Returns:
            (是否成功, 错误信息)
        """
        if Image is None:
            return False, "Pillow 未安装，无法压缩图片"

        try:
            with Image.open(source_path) as img:
                # 处理 RGBA 转 RGB (JPEG 不支持透明通道)
                if img.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                # 逐步降低质量直到满足大小要求
                quality = COMPRESSION_QUALITY_START

                while quality >= COMPRESSION_QUALITY_MIN:
                    img.save(target_path, "JPEG", quality=quality, optimize=True)

                    if target_path.stat().st_size <= max_size:
                        logger.info(f"图片压缩成功: {source_path} -> {target_path}, 质量: {quality}")
                        return True, None

                    quality -= COMPRESSION_QUALITY_STEP

                # 如果还是太大，尝试缩小尺寸
                width, height = img.size
                scale = 0.8

                while scale >= 0.3:
                    new_size = (int(width * scale), int(height * scale))
                    resized = img.resize(new_size, Image.Resampling.LANCZOS)
                    resized.save(target_path, "JPEG", quality=COMPRESSION_QUALITY_MIN, optimize=True)

                    if target_path.stat().st_size <= max_size:
                        logger.info(f"图片压缩成功 (缩放): {source_path}, 比例: {scale}")
                        return True, None

                    scale -= 0.1

                return False, "无法将图片压缩到目标大小"

        except Exception as e:
            return False, f"压缩图片失败: {e}"

    def extract_gif_first_frame(self, source_path: Path, target_path: Path) -> Tuple[bool, Optional[str]]:
        """
        提取 GIF 第一帧

        Args:
            source_path: GIF 文件路径
            target_path: 目标文件路径

        Returns:
            (是否成功, 错误信息)
        """
        if Image is None:
            return False, "Pillow 未安装，无法处理 GIF"

        try:
            with Image.open(source_path) as img:
                # 获取第一帧
                img.seek(0)

                # 转换为 RGB
                if img.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        frame = img.convert("RGBA")
                    else:
                        frame = img
                    background.paste(frame, mask=frame.split()[-1] if frame.mode == "RGBA" else None)
                    frame = background
                else:
                    frame = img.convert("RGB")

                # 保存为 JPEG
                target_path = target_path.with_suffix(".jpg")
                frame.save(target_path, "JPEG", quality=95)
                logger.info(f"GIF 第一帧提取成功: {source_path} -> {target_path}")
                return True, None

        except Exception as e:
            return False, f"提取 GIF 第一帧失败: {e}"

    def load_single(self, source_path: str, force: bool = False) -> LoadResult:
        """
        加载单张图片到缓存

        Args:
            source_path: 源文件路径
            force: 是否强制重新加载（忽略缓存）

        Returns:
            LoadResult
        """
        source_path = self.path_mapper.normalize_path(source_path)
        source = Path(source_path)

        # 检查源文件
        if not source.exists():
            return LoadResult(
                success=False,
                source_path=source_path,
                error=f"源文件不存在: {source_path}",
            )

        original_size = source.stat().st_size

        # 检查缓存
        if not force:
            is_cached, cached_path, md5 = self.is_cached(source_path)
            if is_cached:
                logger.debug(f"使用缓存: {source_path} -> {cached_path}")
                return LoadResult(
                    success=True,
                    source_path=source_path,
                    cached_path=cached_path,
                    md5=md5,
                    original_size=original_size,
                    final_size=Path(cached_path).stat().st_size if cached_path else 0,
                )

        # 计算 MD5
        md5 = self.calculate_md5(source)
        extension = source.suffix.lower()

        # 确定缓存路径
        cached_path = self.get_cached_path(md5, extension)

        was_compressed = False
        was_gif_extracted = False

        try:
            # GIF 处理：提取第一帧
            if extension == ".gif":
                success, error = self.extract_gif_first_frame(source, cached_path)
                if not success:
                    return LoadResult(
                        success=False,
                        source_path=source_path,
                        error=error,
                    )
                was_gif_extracted = True
                cached_path = cached_path.with_suffix(".jpg")

            # 检查是否需要压缩
            elif self.validator.needs_compression(source_path):
                success, error = self.compress_image(source, cached_path)
                if not success:
                    return LoadResult(
                        success=False,
                        source_path=source_path,
                        error=error,
                    )
                was_compressed = True

            else:
                # 直接复制
                shutil.copy2(source, cached_path)

            # 更新缓存元数据
            final_size = cached_path.stat().st_size
            self._cache_meta[md5] = {
                "source_path": source_path,
                "cached_path": str(cached_path),
                "original_size": original_size,
                "final_size": final_size,
                "was_compressed": was_compressed,
                "was_gif_extracted": was_gif_extracted,
            }
            self._save_cache_meta()

            return LoadResult(
                success=True,
                source_path=source_path,
                cached_path=str(cached_path),
                was_compressed=was_compressed,
                was_gif_extracted=was_gif_extracted,
                md5=md5,
                original_size=original_size,
                final_size=final_size,
            )

        except Exception as e:
            logger.error(f"加载图片失败: {source_path}, {e}")
            return LoadResult(
                success=False,
                source_path=source_path,
                error=str(e),
            )

    def load_batch(
        self,
        source_paths: List[str],
        validate_first: bool = True,
        force: bool = False,
    ) -> BatchLoadResult:
        """
        批量加载图片

        Args:
            source_paths: 源文件路径列表
            validate_first: 是否先进行校验
            force: 是否强制重新加载

        Returns:
            BatchLoadResult
        """
        result = BatchLoadResult()

        # 先进行校验
        if validate_first:
            validation = self.validator.validate_batch(source_paths)
            if validation.has_errors:
                for error in validation.errors:
                    result.results.append(LoadResult(
                        success=False,
                        source_path=error.path,
                        error=error.message,
                    ))
                    result.failed_count += 1

                # 只处理有效的路径
                source_paths = validation.valid_paths

        # 加载每张图片
        for path in source_paths:
            load_result = self.load_single(path, force)
            result.results.append(load_result)

            if load_result.success:
                # 检查是否使用了缓存
                is_cached, _, _ = self.is_cached(path)
                if is_cached and not force:
                    result.skipped_count += 1
                else:
                    result.success_count += 1
            else:
                result.failed_count += 1

        return result

    def clear_cache(self) -> int:
        """清理缓存"""
        count = 0
        for file in self.cache_dir.rglob("*"):
            if file.is_file() and file.name != CACHE_META_FILE:
                try:
                    file.unlink()
                    count += 1
                except Exception as e:
                    logger.warning(f"删除缓存文件失败: {file}, {e}")

        self._cache_meta = {}
        self._save_cache_meta()

        return count

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        total_files = 0
        total_size = 0

        for file in self.cache_dir.rglob("*"):
            if file.is_file() and file.name != CACHE_META_FILE:
                total_files += 1
                total_size += file.stat().st_size

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "cache_entries": len(self._cache_meta),
        }


# 全局图片加载器实例
_loader_instance: Optional[ImageLoader] = None


def get_image_loader() -> ImageLoader:
    """获取图片加载器实例（单例）"""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = ImageLoader()
    return _loader_instance


def reset_image_loader() -> None:
    """重置图片加载器实例"""
    global _loader_instance
    _loader_instance = None


def load_images(paths: List[str]) -> BatchLoadResult:
    """便捷函数：加载图片列表"""
    loader = get_image_loader()
    return loader.load_batch(paths)
