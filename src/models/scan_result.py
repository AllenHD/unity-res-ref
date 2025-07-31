"""Unity Resource Reference Scanner - Scan Result Data Model

扫描结果数据模型定义，用于存储扫描任务的执行记录和统计信息。
支持扫描历史追踪、性能分析和增量扫描基础数据。
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Index, Boolean, Float

from .asset import Base


class ScanStatus(str, Enum):
    """扫描状态枚举"""
    PENDING = "pending"         # 待执行
    RUNNING = "running"         # 执行中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"          # 执行失败
    CANCELLED = "cancelled"     # 已取消
    PARTIAL = "partial"        # 部分完成


class ScanType(str, Enum):
    """扫描类型枚举"""
    FULL = "full"              # 全量扫描
    INCREMENTAL = "incremental" # 增量扫描
    SELECTIVE = "selective"     # 选择性扫描
    VALIDATION = "validation"   # 验证扫描


class ScanResult(Base):
    """扫描结果数据模型
    
    存储每次扫描任务的执行记录、统计信息和相关元数据。
    用于扫描历史追踪、性能分析和增量扫描的基础数据。
    """
    __tablename__ = "scan_results"

    # 主键：自增ID
    id = Column(Integer, primary_key=True, autoincrement=True, comment="扫描结果ID")
    
    # 扫描基本信息
    scan_id = Column(String(36), nullable=False, comment="扫描任务唯一标识")
    scan_type = Column(String(20), nullable=False, comment="扫描类型")
    scan_status = Column(String(20), nullable=False, comment="扫描状态")
    
    # 时间信息
    started_at = Column(DateTime, nullable=False, comment="扫描开始时间")
    completed_at = Column(DateTime, nullable=True, comment="扫描完成时间")
    duration_seconds = Column(Float, nullable=True, comment="扫描耗时(秒)")
    
    # 扫描范围和配置
    project_path = Column(String(512), nullable=False, comment="项目路径")
    scan_paths = Column(JSON, nullable=True, comment="扫描路径列表")
    exclude_paths = Column(JSON, nullable=True, comment="排除路径列表")
    file_extensions = Column(JSON, nullable=True, comment="扫描文件扩展名")
    
    # 统计信息
    total_files_scanned = Column(Integer, default=0, comment="扫描文件总数")
    total_assets_found = Column(Integer, default=0, comment="发现资源总数")
    total_dependencies_found = Column(Integer, default=0, comment="发现依赖关系总数")
    new_assets_count = Column(Integer, default=0, comment="新增资源数量")
    updated_assets_count = Column(Integer, default=0, comment="更新资源数量")
    deleted_assets_count = Column(Integer, default=0, comment="删除资源数量")
    
    # 性能统计
    avg_file_scan_time_ms = Column(Float, nullable=True, comment="平均文件扫描时间(毫秒)")
    max_file_scan_time_ms = Column(Float, nullable=True, comment="最大文件扫描时间(毫秒)")
    memory_usage_mb = Column(Float, nullable=True, comment="内存使用量(MB)")
    
    # 错误和警告
    error_count = Column(Integer, default=0, comment="错误数量")
    warning_count = Column(Integer, default=0, comment="警告数量")
    error_messages = Column(JSON, nullable=True, comment="错误消息列表")
    warning_messages = Column(JSON, nullable=True, comment="警告消息列表")
    
    # 扩展信息
    scan_config = Column(JSON, nullable=True, comment="扫描配置快照")
    performance_metrics = Column(JSON, nullable=True, comment="性能指标")
    scan_metadata = Column(JSON, nullable=True, comment="扩展元数据")
    
    # 数据库索引定义
    __table_args__ = (
        Index('idx_scan_result_scan_id', 'scan_id'),
        Index('idx_scan_result_type', 'scan_type'),
        Index('idx_scan_result_status', 'scan_status'),
        Index('idx_scan_result_started_at', 'started_at'),
        Index('idx_scan_result_completed_at', 'completed_at'),
        Index('idx_scan_result_project_path', 'project_path'),
        Index('idx_scan_result_duration', 'duration_seconds'),
        # 复合索引
        Index('idx_scan_result_type_status', 'scan_type', 'scan_status'),
        Index('idx_scan_result_project_started', 'project_path', 'started_at'),
        Index('idx_scan_result_status_completed', 'scan_status', 'completed_at'),
    )

    def __init__(self, scan_id: str, scan_type: str, project_path: str, **kwargs):
        """初始化ScanResult实例
        
        Args:
            scan_id: 扫描任务唯一标识
            scan_type: 扫描类型
            project_path: 项目路径
            **kwargs: 其他可选参数
        """
        self.scan_id = scan_id
        self.scan_type = scan_type
        self.project_path = project_path
        
        # 设置默认值
        self.scan_status = kwargs.get('scan_status', ScanStatus.PENDING.value)
        self.started_at = kwargs.get('started_at', datetime.utcnow())
        self.total_files_scanned = kwargs.get('total_files_scanned', 0)
        self.total_assets_found = kwargs.get('total_assets_found', 0)
        self.total_dependencies_found = kwargs.get('total_dependencies_found', 0)
        self.new_assets_count = kwargs.get('new_assets_count', 0)
        self.updated_assets_count = kwargs.get('updated_assets_count', 0)
        self.deleted_assets_count = kwargs.get('deleted_assets_count', 0)
        self.error_count = kwargs.get('error_count', 0)
        self.warning_count = kwargs.get('warning_count', 0)
        
        # 设置其他属性
        excluded_keys = [
            'scan_status', 'started_at', 'total_files_scanned', 'total_assets_found',
            'total_dependencies_found', 'new_assets_count', 'updated_assets_count',
            'deleted_assets_count', 'error_count', 'warning_count'
        ]
        for key, value in kwargs.items():
            if hasattr(self, key) and key not in excluded_keys:
                setattr(self, key, value)

    @classmethod
    def create_scan_result(
        cls,
        scan_id: str,
        scan_type: ScanType,
        project_path: str,
        scan_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        file_extensions: Optional[List[str]] = None,
        scan_config: Optional[Dict[str, Any]] = None
    ) -> "ScanResult":
        """创建扫描结果实例的便捷方法
        
        Args:
            scan_id: 扫描任务唯一标识
            scan_type: 扫描类型
            project_path: 项目路径
            scan_paths: 扫描路径列表
            exclude_paths: 排除路径列表
            file_extensions: 文件扩展名列表
            scan_config: 扫描配置
            
        Returns:
            ScanResult: 扫描结果实例
        """
        return cls(
            scan_id=scan_id,
            scan_type=scan_type.value,
            project_path=project_path,
            scan_paths=scan_paths or [],
            exclude_paths=exclude_paths or [],
            file_extensions=file_extensions or [],
            scan_config=scan_config or {}
        )

    def start_scan(self) -> None:
        """开始扫描"""
        self.scan_status = ScanStatus.RUNNING.value
        self.started_at = datetime.utcnow()

    def complete_scan(
        self,
        total_files_scanned: int = 0,
        total_assets_found: int = 0,
        total_dependencies_found: int = 0,
        new_assets_count: int = 0,
        updated_assets_count: int = 0,
        deleted_assets_count: int = 0
    ) -> None:
        """完成扫描
        
        Args:
            total_files_scanned: 扫描文件总数
            total_assets_found: 发现资源总数
            total_dependencies_found: 发现依赖关系总数
            new_assets_count: 新增资源数量
            updated_assets_count: 更新资源数量
            deleted_assets_count: 删除资源数量
        """
        self.scan_status = ScanStatus.COMPLETED.value
        self.completed_at = datetime.utcnow()
        
        # 计算扫描耗时
        if self.started_at and self.completed_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        
        # 更新统计信息
        self.total_files_scanned = total_files_scanned
        self.total_assets_found = total_assets_found
        self.total_dependencies_found = total_dependencies_found
        self.new_assets_count = new_assets_count
        self.updated_assets_count = updated_assets_count
        self.deleted_assets_count = deleted_assets_count

    def fail_scan(self, error_message: str) -> None:
        """标记扫描失败
        
        Args:
            error_message: 错误消息
        """
        self.scan_status = ScanStatus.FAILED.value
        self.completed_at = datetime.utcnow()
        
        if self.started_at and self.completed_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        
        self.add_error(error_message)

    def cancel_scan(self) -> None:
        """取消扫描"""
        self.scan_status = ScanStatus.CANCELLED.value
        self.completed_at = datetime.utcnow()
        
        if self.started_at and self.completed_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def add_error(self, error_message: str) -> None:
        """添加错误消息
        
        Args:
            error_message: 错误消息
        """
        if self.error_messages is None:
            self.error_messages = []
        self.error_messages.append({
            'timestamp': datetime.utcnow().isoformat(),
            'message': error_message
        })
        self.error_count = len(self.error_messages)

    def add_warning(self, warning_message: str) -> None:
        """添加警告消息
        
        Args:
            warning_message: 警告消息
        """
        if self.warning_messages is None:
            self.warning_messages = []
        self.warning_messages.append({
            'timestamp': datetime.utcnow().isoformat(),
            'message': warning_message
        })
        self.warning_count = len(self.warning_messages)

    def update_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """更新性能指标
        
        Args:
            metrics: 性能指标字典
        """
        if self.performance_metrics is None:
            self.performance_metrics = {}
        self.performance_metrics.update(metrics)
        
        # 更新标准性能字段
        if 'avg_file_scan_time_ms' in metrics:
            self.avg_file_scan_time_ms = metrics['avg_file_scan_time_ms']
        if 'max_file_scan_time_ms' in metrics:
            self.max_file_scan_time_ms = metrics['max_file_scan_time_ms']
        if 'memory_usage_mb' in metrics:
            self.memory_usage_mb = metrics['memory_usage_mb']

    @property
    def is_completed(self) -> bool:
        """检查扫描是否已完成"""
        status = getattr(self, 'scan_status', ScanStatus.PENDING.value)
        return status in [ScanStatus.COMPLETED.value, ScanStatus.FAILED.value, ScanStatus.CANCELLED.value]

    @property
    def is_successful(self) -> bool:
        """检查扫描是否成功完成"""
        return getattr(self, 'scan_status', ScanStatus.PENDING.value) == ScanStatus.COMPLETED.value

    @property
    def efficiency_ratio(self) -> Optional[float]:
        """计算扫描效率比率（资源数/文件数）"""
        total_files = getattr(self, 'total_files_scanned', 0)
        total_assets = getattr(self, 'total_assets_found', 0)
        if total_files and total_files > 0:
            return total_assets / total_files
        return None

    @property 
    def change_ratio(self) -> Optional[float]:
        """计算变更比率（变更资源数/总资源数）"""
        total_assets = getattr(self, 'total_assets_found', 0)
        changed_assets = (
            getattr(self, 'new_assets_count', 0) +
            getattr(self, 'updated_assets_count', 0) +
            getattr(self, 'deleted_assets_count', 0)
        )
        if total_assets and total_assets > 0:
            return changed_assets / total_assets
        return None

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<ScanResult(scan_id='{self.scan_id}', type='{self.scan_type}', status='{self.scan_status}')>"

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        status = getattr(self, 'scan_status', 'unknown')
        scan_type = getattr(self, 'scan_type', 'unknown')
        return f"Scan {self.scan_id} ({scan_type}): {status}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            Dict[str, Any]: 扫描结果信息字典
        """
        started_at = getattr(self, 'started_at', None)
        completed_at = getattr(self, 'completed_at', None)
        
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'scan_type': getattr(self, 'scan_type', ''),
            'scan_status': getattr(self, 'scan_status', ''),
            'started_at': started_at.isoformat() if started_at else None,
            'completed_at': completed_at.isoformat() if completed_at else None,
            'duration_seconds': getattr(self, 'duration_seconds', None),
            'project_path': getattr(self, 'project_path', ''),
            'scan_paths': getattr(self, 'scan_paths', []),
            'exclude_paths': getattr(self, 'exclude_paths', []),
            'file_extensions': getattr(self, 'file_extensions', []),
            'total_files_scanned': getattr(self, 'total_files_scanned', 0),
            'total_assets_found': getattr(self, 'total_assets_found', 0),
            'total_dependencies_found': getattr(self, 'total_dependencies_found', 0),
            'new_assets_count': getattr(self, 'new_assets_count', 0),
            'updated_assets_count': getattr(self, 'updated_assets_count', 0),
            'deleted_assets_count': getattr(self, 'deleted_assets_count', 0),
            'avg_file_scan_time_ms': getattr(self, 'avg_file_scan_time_ms', None),
            'max_file_scan_time_ms': getattr(self, 'max_file_scan_time_ms', None),
            'memory_usage_mb': getattr(self, 'memory_usage_mb', None),
            'error_count': getattr(self, 'error_count', 0),
            'warning_count': getattr(self, 'warning_count', 0),
            'error_messages': getattr(self, 'error_messages', []),
            'warning_messages': getattr(self, 'warning_messages', []),
            'efficiency_ratio': self.efficiency_ratio,
            'change_ratio': self.change_ratio,
            'is_completed': self.is_completed,
            'is_successful': self.is_successful,
            'scan_config': getattr(self, 'scan_config', {}),
            'performance_metrics': getattr(self, 'performance_metrics', {}),
            'scan_metadata': getattr(self, 'scan_metadata', {}),
        }


class ScanStatistics:
    """扫描统计辅助类
    
    提供扫描结果的统计分析功能。
    """

    @staticmethod
    def calculate_average_scan_time(scan_results: List[ScanResult]) -> Optional[float]:
        """计算平均扫描时间
        
        Args:
            scan_results: 扫描结果列表
            
        Returns:
            Optional[float]: 平均扫描时间（秒）
        """
        valid_durations = [
            getattr(result, 'duration_seconds', 0) 
            for result in scan_results 
            if getattr(result, 'duration_seconds', None) is not None
        ]
        
        if valid_durations:
            return sum(valid_durations) / len(valid_durations)
        return None

    @staticmethod
    def get_scan_success_rate(scan_results: List[ScanResult]) -> float:
        """计算扫描成功率
        
        Args:
            scan_results: 扫描结果列表
            
        Returns:
            float: 成功率（0.0-1.0）
        """
        if not scan_results:
            return 0.0
        
        successful_scans = sum(
            1 for result in scan_results
            if getattr(result, 'scan_status', '') == ScanStatus.COMPLETED.value
        )
        
        return successful_scans / len(scan_results)

    @staticmethod
    def get_performance_trends(scan_results: List[ScanResult], limit: int = 10) -> Dict[str, List[float]]:
        """获取性能趋势数据
        
        Args:
            scan_results: 扫描结果列表（按时间排序）
            limit: 返回的最近记录数量
            
        Returns:
            Dict[str, List[float]]: 性能趋势数据
        """
        recent_results = scan_results[-limit:] if len(scan_results) > limit else scan_results
        
        trends = {
            'duration_seconds': [],
            'total_files_scanned': [],
            'total_assets_found': [],
            'avg_file_scan_time_ms': [],
            'memory_usage_mb': []
        }
        
        for result in recent_results:
            trends['duration_seconds'].append(getattr(result, 'duration_seconds', 0) or 0)
            trends['total_files_scanned'].append(getattr(result, 'total_files_scanned', 0))
            trends['total_assets_found'].append(getattr(result, 'total_assets_found', 0))
            trends['avg_file_scan_time_ms'].append(getattr(result, 'avg_file_scan_time_ms', 0) or 0)
            trends['memory_usage_mb'].append(getattr(result, 'memory_usage_mb', 0) or 0)
        
        return trends
