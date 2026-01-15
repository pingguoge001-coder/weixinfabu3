"""路径映射器模块"""

import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_SHARE_ROOT = r"Z:\publish"
DEFAULT_CACHE_DIR = Path.home() / ".wechat_publish" / "cache" / "images"


class PathMapper:
    """路径映射器：共享文件夹路径 <-> 本地缓存路径转换"""

    def __init__(
        self,
        share_root: Optional[str] = None,
        cache_dir: Optional[Path] = None,
    ):
        """
        初始化路径映射器

        Args:
            share_root: 共享文件夹根目录 (如 Z:\\publish)
            cache_dir: 本地缓存目录
        """
        self.share_root = Path(share_root) if share_root else Path(DEFAULT_SHARE_ROOT)
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """确保缓存目录存在"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def normalize_path(self, path: str) -> str:
        """
        规范化路径

        - 统一使用正斜杠或反斜杠
        - 去除多余空格
        - 处理相对路径
        """
        if not path:
            return ""

        # 去除首尾空格
        path = path.strip()

        # 去除引号
        path = path.strip("'\"")

        # 规范化路径分隔符 (Windows 使用反斜杠)
        if os.name == "nt":
            path = path.replace("/", "\\")
        else:
            path = path.replace("\\", "/")

        # 处理多余的分隔符
        sep = "\\" if os.name == "nt" else "/"
        while sep + sep in path:
            path = path.replace(sep + sep, sep)

        return path

    def is_share_path(self, path: str) -> bool:
        """判断是否为共享路径"""
        normalized = self.normalize_path(path)
        share_str = str(self.share_root).lower()
        return normalized.lower().startswith(share_str)

    def is_unc_path(self, path: str) -> bool:
        """判断是否为 UNC 路径 (\\\\server\\share)"""
        return path.startswith("\\\\") or path.startswith("//")

    def is_absolute_path(self, path: str) -> bool:
        """判断是否为绝对路径"""
        p = Path(path)
        return p.is_absolute()

    def share_to_cache(self, share_path: str) -> Path:
        """
        将共享路径转换为本地缓存路径

        Args:
            share_path: 共享文件夹路径

        Returns:
            本地缓存路径
        """
        normalized = self.normalize_path(share_path)
        share_path_obj = Path(normalized)

        try:
            # 获取相对于共享根目录的路径
            relative = share_path_obj.relative_to(self.share_root)
            cache_path = self.cache_dir / relative
        except ValueError:
            # 如果不在共享根目录下，使用文件名
            cache_path = self.cache_dir / share_path_obj.name

        return cache_path

    def cache_to_share(self, cache_path: Path) -> Optional[str]:
        """
        将本地缓存路径转换回共享路径

        Args:
            cache_path: 本地缓存路径

        Returns:
            共享文件夹路径，如果无法转换则返回 None
        """
        try:
            relative = cache_path.relative_to(self.cache_dir)
            return str(self.share_root / relative)
        except ValueError:
            return None

    def resolve_path(self, path: str, base_dir: Optional[str] = None) -> str:
        """
        解析路径（处理相对路径）

        Args:
            path: 输入路径
            base_dir: 基准目录（用于解析相对路径）

        Returns:
            解析后的绝对路径
        """
        normalized = self.normalize_path(path)

        if self.is_absolute_path(normalized):
            return normalized

        # 相对路径处理
        if base_dir:
            base = Path(base_dir)
            if base.is_file():
                base = base.parent
            resolved = base / normalized
            return str(resolved.resolve())

        # 默认相对于共享根目录
        resolved = self.share_root / normalized
        return str(resolved)

    def split_paths(self, paths_str: str) -> List[str]:
        """
        分割路径字符串

        支持以下分隔符：
        - 分号 ;
        - 换行符
        - 逗号 , (如果不是路径的一部分)
        """
        if not paths_str:
            return []

        # 首先按分号和换行分割
        paths = re.split(r"[;\n]", paths_str)

        # 过滤空字符串并规范化
        result = []
        for p in paths:
            p = p.strip()
            if p:
                # 如果包含逗号但不像是路径的一部分，则进一步分割
                if "," in p and not re.match(r"^[A-Za-z]:", p):
                    sub_paths = p.split(",")
                    for sp in sub_paths:
                        sp = sp.strip()
                        if sp:
                            result.append(self.normalize_path(sp))
                else:
                    result.append(self.normalize_path(p))

        return result

    def validate_path(self, path: str) -> Tuple[bool, Optional[str]]:
        """
        验证路径有效性

        Returns:
            (是否有效, 错误信息)
        """
        if not path:
            return False, "路径为空"

        normalized = self.normalize_path(path)
        path_obj = Path(normalized)

        # 检查路径是否存在
        if not path_obj.exists():
            # 检查是否是共享路径但网络不可达
            if self.is_share_path(normalized) or self.is_unc_path(normalized):
                return False, f"网络路径不可达: {normalized}"
            return False, f"路径不存在: {normalized}"

        return True, None

    def get_cache_path_for_file(self, file_path: str, preserve_structure: bool = True) -> Path:
        """
        获取文件的缓存路径

        Args:
            file_path: 原始文件路径
            preserve_structure: 是否保持目录结构

        Returns:
            缓存路径
        """
        normalized = self.normalize_path(file_path)
        path_obj = Path(normalized)

        if preserve_structure and self.is_share_path(normalized):
            return self.share_to_cache(normalized)
        else:
            # 不保持结构，直接放在缓存根目录
            return self.cache_dir / path_obj.name

    def clear_cache(self) -> int:
        """
        清理缓存目录

        Returns:
            删除的文件数量
        """
        count = 0
        if self.cache_dir.exists():
            for file in self.cache_dir.rglob("*"):
                if file.is_file():
                    try:
                        file.unlink()
                        count += 1
                    except Exception as e:
                        logger.warning(f"删除缓存文件失败: {file}, {e}")

        return count


# 全局路径映射器实例
_mapper_instance: Optional[PathMapper] = None


def get_path_mapper(
    share_root: Optional[str] = None,
    cache_dir: Optional[Path] = None,
) -> PathMapper:
    """获取路径映射器实例（单例）"""
    global _mapper_instance
    if _mapper_instance is None:
        _mapper_instance = PathMapper(share_root, cache_dir)
    return _mapper_instance


def reset_path_mapper() -> None:
    """重置路径映射器实例"""
    global _mapper_instance
    _mapper_instance = None
