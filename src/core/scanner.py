"""核心文件扫描器实现

提供高效的文件系统扫描功能，支持配置化路径、过滤和进度报告。
"""

import time
import threading
from pathlib import Path
from typing import List, Dict, Set, Optional, Union, Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from ..core.config import ScanConfig
from ..utils.path_utils import PathMatcher, PathUtils, is_unity_project_directory
from ..utils.file_watcher import FileChangeDetector, IncrementalScanner, ScanSession

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """扫描结果数据类"""
    session_id: str
    project_path: Path
    total_files: int = 0
    scanned_files: int = 0
    filtered_files: int = 0
    error_files: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    file_paths: List[Path] = field(default_factory=list)
    
    @property
    def duration(self) -> Optional[float]:
        """获取扫描持续时间（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def success_rate(self) -> float:
        """获取扫描成功率"""
        if self.scanned_files == 0:
            return 0.0
        return ((self.scanned_files - self.error_files) / self.scanned_files) * 100
    
    def to_dict(self) -> Dict[str, any]:
        """转换为字典格式"""
        return {
            'session_id': self.session_id,
            'project_path': str(self.project_path),
            'total_files': self.total_files,
            'scanned_files': self.scanned_files,
            'filtered_files': self.filtered_files,
            'error_files': self.error_files,
            'duration': self.duration,
            'success_rate': self.success_rate,
            'errors': self.errors,
            'file_count': len(self.file_paths)
        }


class ProgressReporter:
    """扫描进度报告器"""
    
    def __init__(self, callback: Optional[Callable[[Dict], None]] = None):
        """初始化进度报告器
        
        Args:
            callback: 进度回调函数，接收进度信息字典
        """
        self.callback = callback
        self.start_time: Optional[datetime] = None
        self.last_report_time: Optional[datetime] = None
        self.report_interval = 1.0  # 报告间隔（秒）
        
        # 统计信息
        self.processed_files = 0
        self.total_files = 0
        self.current_path: Optional[Path] = None
        
        # 线程安全锁
        self._lock = threading.Lock()
    
    def start(self, total_files: int = 0) -> None:
        """开始进度报告
        
        Args:
            total_files: 预计总文件数
        """
        with self._lock:
            self.start_time = datetime.now()
            self.last_report_time = self.start_time
            self.total_files = total_files
            self.processed_files = 0
            self._report_progress()
    
    def update(self, processed_files: int = None, current_path: Path = None) -> None:
        """更新进度
        
        Args:
            processed_files: 已处理文件数
            current_path: 当前处理的文件路径
        """
        with self._lock:
            if processed_files is not None:
                self.processed_files = processed_files
            else:
                self.processed_files += 1
                
            if current_path is not None:
                self.current_path = current_path
            
            # 检查是否需要报告进度
            current_time = datetime.now()
            if (current_time - self.last_report_time).total_seconds() >= self.report_interval:
                self._report_progress()
                self.last_report_time = current_time
    
    def finish(self) -> None:
        """完成进度报告"""
        with self._lock:
            self._report_progress(finished=True)
    
    def _report_progress(self, finished: bool = False) -> None:
        """内部进度报告方法"""
        if not self.callback:
            return
            
        current_time = datetime.now()
        elapsed_time = (current_time - self.start_time).total_seconds() if self.start_time else 0
        
        # 计算进度百分比
        progress_percent = 0.0
        if self.total_files > 0:
            progress_percent = (self.processed_files / self.total_files) * 100
        
        # 估算剩余时间
        estimated_total_time = None
        estimated_remaining_time = None
        
        if self.processed_files > 0 and self.total_files > 0:
            estimated_total_time = elapsed_time * (self.total_files / self.processed_files)
            estimated_remaining_time = estimated_total_time - elapsed_time
        
        # 计算处理速度
        files_per_second = self.processed_files / elapsed_time if elapsed_time > 0 else 0
        
        progress_info = {
            'processed_files': self.processed_files,
            'total_files': self.total_files,
            'progress_percent': progress_percent,
            'elapsed_time': elapsed_time,
            'estimated_remaining_time': estimated_remaining_time,
            'files_per_second': files_per_second,
            'current_path': str(self.current_path) if self.current_path else None,
            'finished': finished
        }
        
        try:
            self.callback(progress_info)
        except Exception as e:
            logger.error(f"进度报告回调函数执行失败: {e}")


class FileScanner:
    """高效的文件系统扫描器"""
    
    def __init__(self, config: ScanConfig):
        """初始化文件扫描器
        
        Args:
            config: 扫描配置
        """
        self.config = config
        
        # 创建路径匹配器
        self.exclude_matcher = PathMatcher(
            config.exclude_paths, 
            case_sensitive=True
        )
        
        # 标准化文件扩展名
        self.file_extensions = set()
        for ext in config.file_extensions:
            if not ext.startswith('.'):
                ext = '.' + ext
            self.file_extensions.add(ext.lower())
        
        # 文件大小限制（字节）
        self.max_file_size = config.max_file_size_mb * 1024 * 1024
        
        # 进度报告器
        self.progress_reporter: Optional[ProgressReporter] = None
        
        # 线程池
        self.thread_pool: Optional[ThreadPoolExecutor] = None
        
        logger.info(f"文件扫描器初始化完成，扫描扩展名: {self.file_extensions}")
    
    def set_progress_callback(self, callback: Callable[[Dict], None]) -> None:
        """设置进度回调函数
        
        Args:
            callback: 进度回调函数
        """
        self.progress_reporter = ProgressReporter(callback)
    
    def _should_scan_file(self, file_path: Path) -> bool:
        """判断是否应该扫描文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            应该扫描返回True，否则返回False
        """
        # 检查文件扩展名
        if file_path.suffix.lower() not in self.file_extensions:
            return False
        
        # 检查是否为隐藏文件
        if self.config.ignore_hidden_files:
            if file_path.name.startswith('.'):
                return False
            # 检查路径中是否包含隐藏目录
            if any(part.startswith('.') for part in file_path.parts):
                return False
        
        # 检查文件大小
        try:
            if file_path.stat().st_size > self.max_file_size:
                logger.debug(f"文件过大，跳过: {file_path}")
                return False
        except OSError as e:
            logger.warning(f"无法获取文件大小 {file_path}: {e}")
            return False
        
        return True
    
    def _should_exclude_path(self, path: Path, base_path: Path) -> bool:
        """判断是否应该排除路径
        
        Args:
            path: 要检查的路径
            base_path: 基础路径
            
        Returns:
            应该排除返回True，否则返回False
        """
        try:
            # 获取相对路径
            relative_path = path.relative_to(base_path)
            
            # 使用路径匹配器检查排除模式
            return self.exclude_matcher.matches(relative_path)
            
        except ValueError:
            # 如果无法计算相对路径，默认不排除
            return False
    
    def _scan_directory(self, directory: Path, base_path: Path) -> Iterator[Path]:
        """扫描单个目录
        
        Args:
            directory: 要扫描的目录
            base_path: 基础路径（用于计算相对路径）
            
        Yields:
            符合条件的文件路径
        """
        if not directory.exists() or not directory.is_dir():
            return
        
        try:
            for item in directory.iterdir():
                # 检查是否应该排除
                if self._should_exclude_path(item, base_path):
                    logger.debug(f"路径被排除: {item}")
                    continue
                
                if item.is_file():
                    if self._should_scan_file(item):
                        yield item
                        
                elif item.is_dir():
                    # 递归扫描子目录
                    yield from self._scan_directory(item, base_path)
                    
        except PermissionError as e:
            logger.warning(f"权限不足，无法访问目录 {directory}: {e}")
        except OSError as e:
            logger.warning(f"扫描目录时发生错误 {directory}: {e}")
    
    def _count_files(self, scan_paths: List[Path]) -> int:
        """预先计算要扫描的文件总数
        
        Args:
            scan_paths: 扫描路径列表
            
        Returns:
            预计文件总数
        """
        total_count = 0
        
        for base_path in scan_paths:
            if not base_path.exists():
                continue
                
            try:
                for file_path in self._scan_directory(base_path, base_path):
                    total_count += 1
            except Exception as e:
                logger.error(f"计算文件数量时发生错误 {base_path}: {e}")
        
        return total_count
    
    def scan_project(self, project_path: Union[str, Path]) -> ScanResult:
        """扫描Unity项目
        
        Args:
            project_path: Unity项目根路径
            
        Returns:
            扫描结果
        """
        project_path = Path(project_path).resolve()
        
        # 验证Unity项目
        if not is_unity_project_directory(project_path):
            raise ValueError(f"指定路径不是有效的Unity项目: {project_path}")
        
        # 构建扫描路径
        scan_paths = []
        for path_pattern in self.config.paths:
            scan_path = project_path / path_pattern
            if scan_path.exists():
                scan_paths.append(scan_path)
            else:
                logger.warning(f"扫描路径不存在: {scan_path}")
        
        if not scan_paths:
            raise ValueError("没有有效的扫描路径")
        
        # 生成会话ID
        session_id = f"scan_{int(time.time())}"
        
        # 创建扫描结果
        result = ScanResult(
            session_id=session_id,
            project_path=project_path,
            start_time=datetime.now(timezone.utc)
        )
        
        logger.info(f"开始扫描Unity项目: {project_path}")
        logger.info(f"扫描路径: {[str(p) for p in scan_paths]}")
        
        try:
            # 预计算文件总数（用于进度报告）
            if self.progress_reporter:
                logger.info("正在计算文件总数...")
                total_files = self._count_files(scan_paths)
                result.total_files = total_files
                self.progress_reporter.start(total_files)
                logger.info(f"预计扫描文件数: {total_files}")
            
            # 扫描所有路径
            for base_path in scan_paths:
                logger.info(f"扫描路径: {base_path}")
                
                for file_path in self._scan_directory(base_path, base_path):
                    result.file_paths.append(file_path)
                    result.scanned_files += 1
                    
                    # 更新进度
                    if self.progress_reporter:
                        self.progress_reporter.update(
                            processed_files=result.scanned_files,
                            current_path=file_path
                        )
            
            # 完成扫描
            result.end_time = datetime.now(timezone.utc)
            
            if self.progress_reporter:
                self.progress_reporter.finish()
            
            logger.info(f"扫描完成: {result.scanned_files} 个文件，"
                       f"耗时: {result.duration:.2f} 秒")
            
            return result
            
        except Exception as e:
            error_msg = f"扫描过程中发生错误: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            result.error_files += 1
            result.end_time = datetime.now(timezone.utc)
            raise
    
    def scan_paths(self, paths: List[Union[str, Path]]) -> ScanResult:
        """扫描指定路径列表
        
        Args:
            paths: 要扫描的路径列表
            
        Returns:
            扫描结果
        """
        scan_paths = [Path(p).resolve() for p in paths]
        
        # 生成会话ID
        session_id = f"scan_{int(time.time())}"
        
        # 创建扫描结果
        result = ScanResult(
            session_id=session_id,
            project_path=scan_paths[0].parent if scan_paths else Path.cwd(),
            start_time=datetime.now(timezone.utc)
        )
        
        logger.info(f"开始扫描指定路径: {[str(p) for p in scan_paths]}")
        
        try:
            # 预计算文件总数
            if self.progress_reporter:
                total_files = self._count_files(scan_paths)
                result.total_files = total_files
                self.progress_reporter.start(total_files)
            
            # 扫描所有路径
            for path in scan_paths:
                if path.is_file():
                    if self._should_scan_file(path):
                        result.file_paths.append(path)
                        result.scanned_files += 1
                elif path.is_dir():
                    for file_path in self._scan_directory(path, path):
                        result.file_paths.append(file_path)
                        result.scanned_files += 1
                        
                        # 更新进度
                        if self.progress_reporter:
                            self.progress_reporter.update(
                                processed_files=result.scanned_files,
                                current_path=file_path
                            )
            
            result.end_time = datetime.now(timezone.utc)
            
            if self.progress_reporter:
                self.progress_reporter.finish()
            
            logger.info(f"路径扫描完成: {result.scanned_files} 个文件")
            return result
            
        except Exception as e:
            error_msg = f"路径扫描过程中发生错误: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            result.error_files += 1
            result.end_time = datetime.now(timezone.utc)
            raise
    
    def get_scanner_stats(self) -> Dict[str, any]:
        """获取扫描器统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'file_extensions': list(self.file_extensions),
            'max_file_size_mb': self.config.max_file_size_mb,
            'exclude_patterns': self.config.exclude_paths,
            'ignore_hidden_files': self.config.ignore_hidden_files,
            'scan_paths': self.config.paths
        }


class IncrementalFileScanner:
    """增量文件扫描器，基于FileScanner和IncrementalScanner"""
    
    def __init__(
        self, 
        config: ScanConfig,
        cache_file: Optional[Path] = None,
        enable_checksum: bool = False
    ):
        """初始化增量文件扫描器
        
        Args:
            config: 扫描配置
            cache_file: 缓存文件路径
            enable_checksum: 是否启用文件校验和
        """
        self.config = config
        self.file_scanner = FileScanner(config)
        
        # 创建文件变更检测器
        self.change_detector = FileChangeDetector(cache_file, enable_checksum)
        
        # 当前扫描会话
        self.current_session: Optional[ScanSession] = None
    
    def set_progress_callback(self, callback: Callable[[Dict], None]) -> None:
        """设置进度回调函数"""
        self.file_scanner.set_progress_callback(callback)
    
    def full_scan(self, project_path: Union[str, Path]) -> ScanResult:
        """执行完全扫描
        
        Args:
            project_path: Unity项目路径
            
        Returns:
            扫描结果
        """
        # 清除缓存，强制重新扫描所有文件
        self.change_detector.clear_cache()
        
        # 执行完全扫描
        result = self.file_scanner.scan_project(project_path)
        
        # 更新缓存
        for file_path in result.file_paths:
            self.change_detector.update_file_cache(file_path)
        
        # 保存缓存
        self.change_detector.save_cache()
        
        return result
    
    def incremental_scan(self, project_path: Union[str, Path]) -> Dict[str, List[Path]]:
        """执行增量扫描
        
        Args:
            project_path: Unity项目路径
            
        Returns:
            包含变更文件的字典
        """
        project_path = Path(project_path).resolve()
        
        # 构建扫描路径
        scan_paths = []
        for path_pattern in self.config.paths:
            scan_path = project_path / path_pattern
            if scan_path.exists():
                scan_paths.append(scan_path)
        
        # 创建增量扫描器
        incremental_scanner = IncrementalScanner(
            self.change_detector,
            scan_paths,
            self.config.file_extensions
        )
        
        # 开始扫描会话
        session_id = incremental_scanner.start_scan_session()
        logger.info(f"开始增量扫描: {session_id}")
        
        try:
            # 扫描变更
            changes = incremental_scanner.scan_for_changes()
            
            # 结束会话
            self.current_session = incremental_scanner.end_scan_session()
            
            logger.info(f"增量扫描完成: 修改 {len(changes['modified'])} 个，"
                       f"新增 {len(changes['new'])} 个，"
                       f"删除 {len(changes['deleted'])} 个文件")
            
            return changes
            
        except Exception as e:
            logger.error(f"增量扫描失败: {e}")
            incremental_scanner.end_scan_session()
            raise
    
    def get_cache_stats(self) -> Dict[str, any]:
        """获取缓存统计信息"""
        return self.change_detector.get_cache_stats()


def create_file_scanner(config: Optional[ScanConfig] = None) -> FileScanner:
    """创建文件扫描器的便捷函数
    
    Args:
        config: 扫描配置，None时使用默认配置
        
    Returns:
        FileScanner实例
    """
    if config is None:
        # 使用默认配置
        from ..core.config import get_config
        full_config = get_config()
        config = full_config.scan
    
    return FileScanner(config)


def create_incremental_scanner(
    config: Optional[ScanConfig] = None,
    cache_file: Optional[Union[str, Path]] = None,
    enable_checksum: bool = False
) -> IncrementalFileScanner:
    """创建增量文件扫描器的便捷函数
    
    Args:
        config: 扫描配置
        cache_file: 缓存文件路径
        enable_checksum: 是否启用校验和
        
    Returns:
        IncrementalFileScanner实例
    """
    if config is None:
        from ..core.config import get_config
        full_config = get_config()
        config = full_config.scan
    
    cache_path = Path(cache_file) if cache_file else None
    return IncrementalFileScanner(config, cache_path, enable_checksum)
