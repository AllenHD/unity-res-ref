"""文件变更监控模块

提供文件变更检测、监控和缓存功能。
"""

import time
import hashlib
import pickle
from pathlib import Path
from typing import Dict, Set, Optional, Union, NamedTuple, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class FileInfo(NamedTuple):
    """文件信息结构"""
    path: str
    size: int
    mtime: float
    checksum: Optional[str] = None


@dataclass
class ScanSession:
    """扫描会话信息"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    scanned_files: int = 0
    modified_files: int = 0
    new_files: int = 0
    deleted_files: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def duration(self) -> Optional[float]:
        """获取扫描持续时间（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def is_completed(self) -> bool:
        """检查扫描是否完成"""
        return self.end_time is not None


class FileChangeDetector:
    """文件变更检测器"""
    
    def __init__(self, cache_file: Optional[Path] = None, enable_checksum: bool = False):
        """初始化文件变更检测器
        
        Args:
            cache_file: 缓存文件路径，None表示不使用持久化缓存
            enable_checksum: 是否启用文件校验和检测
        """
        self.cache_file = cache_file
        self.enable_checksum = enable_checksum
        self.file_cache: Dict[str, FileInfo] = {}
        self.last_scan_time: Optional[datetime] = None
        
        # 加载缓存
        if self.cache_file and self.cache_file.exists():
            self._load_cache()
    
    def _calculate_checksum(self, file_path: Path, chunk_size: int = 8192) -> Optional[str]:
        """计算文件校验和
        
        Args:
            file_path: 文件路径
            chunk_size: 读取块大小
            
        Returns:
            文件MD5校验和，失败时返回None
        """
        if not self.enable_checksum:
            return None
            
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
            
        except (OSError, IOError) as e:
            logger.warning(f"无法计算文件校验和 {file_path}: {e}")
            return None
    
    def _get_file_info(self, file_path: Path) -> Optional[FileInfo]:
        """获取文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息，失败时返回None
        """
        try:
            stat = file_path.stat()
            checksum = self._calculate_checksum(file_path) if self.enable_checksum else None
            
            return FileInfo(
                path=str(file_path),
                size=stat.st_size,
                mtime=stat.st_mtime,
                checksum=checksum
            )
            
        except OSError as e:
            logger.warning(f"无法获取文件信息 {file_path}: {e}")
            return None
    
    def is_file_modified(self, file_path: Path) -> bool:
        """检查文件是否被修改
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件被修改返回True，否则返回False
        """
        current_info = self._get_file_info(file_path)
        if not current_info:
            return False
            
        cached_info = self.file_cache.get(str(file_path))
        if not cached_info:
            # 新文件
            return True
        
        # 比较文件信息
        if current_info.size != cached_info.size:
            return True
            
        if abs(current_info.mtime - cached_info.mtime) > 1.0:  # 1秒容差
            return True
            
        # 如果启用校验和，比较校验和
        if self.enable_checksum and current_info.checksum and cached_info.checksum:
            if current_info.checksum != cached_info.checksum:
                return True
                
        return False
    
    def update_file_cache(self, file_path: Path) -> bool:
        """更新文件缓存信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            更新成功返回True，失败返回False
        """
        file_info = self._get_file_info(file_path)
        if file_info:
            self.file_cache[str(file_path)] = file_info
            return True
        return False
    
    def remove_from_cache(self, file_path: Path) -> bool:
        """从缓存中移除文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            移除成功返回True，文件不存在返回False
        """
        file_path_str = str(file_path)
        if file_path_str in self.file_cache:
            del self.file_cache[file_path_str]
            return True
        return False
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息
        
        Returns:
            包含统计信息的字典
        """
        total_files = len(self.file_cache)
        total_size = sum(info.size for info in self.file_cache.values())
        
        return {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'checksum_enabled': self.enable_checksum
        }
    
    def _save_cache(self) -> bool:
        """保存缓存到文件
        
        Returns:
            保存成功返回True，失败返回False
        """
        if not self.cache_file:
            return False
            
        try:
            # 确保目录存在
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            cache_data = {
                'file_cache': self.file_cache,
                'last_scan_time': self.last_scan_time,
                'enable_checksum': self.enable_checksum,
                'version': '1.0'
            }
            
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
                
            logger.debug(f"缓存已保存到 {self.cache_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存缓存失败 {self.cache_file}: {e}")
            return False
    
    def _load_cache(self) -> bool:
        """从文件加载缓存
        
        Returns:
            加载成功返回True，失败返回False
        """
        if not self.cache_file or not self.cache_file.exists():
            return False
            
        try:
            with open(self.cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            # 验证缓存版本
            if cache_data.get('version') != '1.0':
                logger.warning("缓存文件版本不匹配，将重新构建缓存")
                return False
            
            self.file_cache = cache_data.get('file_cache', {})
            self.last_scan_time = cache_data.get('last_scan_time')
            
            # 检查校验和设置是否匹配
            cached_checksum_enabled = cache_data.get('enable_checksum', False)
            if cached_checksum_enabled != self.enable_checksum:
                logger.info("校验和设置已更改，将重新构建缓存")
                self.file_cache.clear()
                return False
            
            logger.debug(f"缓存已从 {self.cache_file} 加载，包含 {len(self.file_cache)} 个文件")
            return True
            
        except Exception as e:
            logger.error(f"加载缓存失败 {self.cache_file}: {e}")
            self.file_cache.clear()
            return False
    
    def save_cache(self) -> bool:
        """公开的保存缓存方法"""
        return self._save_cache()
    
    def clear_cache(self) -> None:
        """清除所有缓存"""
        self.file_cache.clear()
        self.last_scan_time = None
        
        if self.cache_file and self.cache_file.exists():
            try:
                self.cache_file.unlink()
                logger.info(f"缓存文件已删除: {self.cache_file}")
            except OSError as e:
                logger.error(f"删除缓存文件失败: {e}")


class IncrementalScanner:
    """增量扫描器"""
    
    def __init__(
        self, 
        change_detector: FileChangeDetector,
        base_paths: List[Path],
        file_extensions: List[str]
    ):
        """初始化增量扫描器
        
        Args:
            change_detector: 文件变更检测器
            base_paths: 基础扫描路径列表
            file_extensions: 关注的文件扩展名列表
        """
        self.change_detector = change_detector
        self.base_paths = base_paths
        self.file_extensions = set(ext.lower() for ext in file_extensions)
        self.current_session: Optional[ScanSession] = None
    
    def start_scan_session(self) -> str:
        """开始新的扫描会话
        
        Returns:
            扫描会话ID
        """
        session_id = f"scan_{int(time.time())}"
        self.current_session = ScanSession(
            session_id=session_id,
            start_time=datetime.now(timezone.utc)
        )
        
        logger.info(f"开始扫描会话: {session_id}")
        return session_id
    
    def end_scan_session(self) -> Optional[ScanSession]:
        """结束当前扫描会话
        
        Returns:
            完成的扫描会话，如果没有活动会话则返回None
        """
        if not self.current_session:
            return None
            
        self.current_session.end_time = datetime.now(timezone.utc)
        completed_session = self.current_session
        self.current_session = None
        
        # 保存缓存
        self.change_detector.save_cache()
        
        logger.info(f"扫描会话完成: {completed_session.session_id}, "
                   f"耗时: {completed_session.duration:.2f}秒")
        
        return completed_session
    
    def scan_for_changes(self) -> Dict[str, List[Path]]:
        """扫描文件变更
        
        Returns:
            包含变更文件分类的字典
        """
        if not self.current_session:
            raise RuntimeError("没有活动的扫描会话，请先调用start_scan_session()")
        
        changes = {
            'modified': [],
            'new': [],
            'deleted': []
        }
        
        # 当前文件集合
        current_files: Set[Path] = set()
        
        # 扫描所有指定路径
        for base_path in self.base_paths:
            if not base_path.exists():
                logger.warning(f"扫描路径不存在: {base_path}")
                continue
                
            try:
                for file_path in base_path.rglob('*'):
                    if not file_path.is_file():
                        continue
                        
                    # 检查文件扩展名
                    if file_path.suffix.lower() not in self.file_extensions:
                        continue
                        
                    current_files.add(file_path)
                    self.current_session.scanned_files += 1
                    
                    # 检查文件是否被修改
                    if self.change_detector.is_file_modified(file_path):
                        # 判断是新文件还是修改文件
                        if str(file_path) in self.change_detector.file_cache:
                            changes['modified'].append(file_path)
                            self.current_session.modified_files += 1
                        else:
                            changes['new'].append(file_path)
                            self.current_session.new_files += 1
                        
                        # 更新缓存
                        self.change_detector.update_file_cache(file_path)
                        
            except OSError as e:
                error_msg = f"扫描路径时发生错误 {base_path}: {e}"
                logger.error(error_msg)
                self.current_session.errors.append(error_msg)
        
        # 检查已删除的文件
        cached_files = set(Path(path) for path in self.change_detector.file_cache.keys())
        deleted_files = cached_files - current_files
        
        for deleted_file in deleted_files:
            changes['deleted'].append(deleted_file)
            self.change_detector.remove_from_cache(deleted_file)
            self.current_session.deleted_files += 1
        
        return changes
    
    def get_scan_progress(self) -> Optional[Dict[str, any]]:
        """获取扫描进度信息
        
        Returns:
            包含进度信息的字典，没有活动会话时返回None
        """
        if not self.current_session:
            return None
            
        current_time = datetime.now(timezone.utc)
        elapsed_time = (current_time - self.current_session.start_time).total_seconds()
        
        return {
            'session_id': self.current_session.session_id,
            'elapsed_time': elapsed_time,
            'scanned_files': self.current_session.scanned_files,
            'modified_files': self.current_session.modified_files,
            'new_files': self.current_session.new_files,
            'deleted_files': self.current_session.deleted_files,
            'errors': len(self.current_session.errors)
        }


def create_change_detector(
    cache_file: Optional[Union[str, Path]] = None,
    enable_checksum: bool = False
) -> FileChangeDetector:
    """创建文件变更检测器的便捷函数
    
    Args:
        cache_file: 缓存文件路径
        enable_checksum: 是否启用校验和检测
        
    Returns:
        FileChangeDetector实例
    """
    cache_path = Path(cache_file) if cache_file else None
    return FileChangeDetector(cache_path, enable_checksum)


def create_incremental_scanner(
    base_paths: List[Union[str, Path]],
    file_extensions: List[str],
    cache_file: Optional[Union[str, Path]] = None,
    enable_checksum: bool = False
) -> IncrementalScanner:
    """创建增量扫描器的便捷函数
    
    Args:
        base_paths: 基础扫描路径列表
        file_extensions: 文件扩展名列表
        cache_file: 缓存文件路径
        enable_checksum: 是否启用校验和检测
        
    Returns:
        IncrementalScanner实例
    """
    change_detector = create_change_detector(cache_file, enable_checksum)
    paths = [Path(p) for p in base_paths]
    return IncrementalScanner(change_detector, paths, file_extensions)
