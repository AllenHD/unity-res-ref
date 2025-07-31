"""Unity Resource Reference Scanner - 核心模块

提供Unity资源依赖关系的核心管理和分析功能：
- 依赖关系图构建和管理
- 数据库持久化操作
- 查询引擎和缓存系统
- 循环依赖检测和分析
"""

from .dependency_graph import (
    DependencyGraph,
    DependencyQueryEngine, 
    DependencyGraphBuilder,
    QueryOptions,
    QueryResult
)

from .database import (
    DatabaseManager,
    get_asset_dao,
    get_dependency_dao
)

from .circular_dependency_analyzer import (
    CircularDependencyAnalyzer,
    CycleType,
    CycleSeverity,
    CycleInfo,
    CycleAnalysisReport
)

__all__ = [
    # 依赖图核心
    'DependencyGraph',
    'DependencyQueryEngine',
    'DependencyGraphBuilder',
    'QueryOptions',
    'QueryResult',
    
    # 数据库管理
    'DatabaseManager',
    'get_asset_dao',
    'get_dependency_dao',
    
    # 循环依赖分析
    'CircularDependencyAnalyzer',
    'CycleType',
    'CycleSeverity',
    'CycleInfo',
    'CycleAnalysisReport',
]

from .config import (
    AppConfig, 
    ScanConfig, 
    DatabaseConfig,
    get_config,
    get_config_manager,
    reload_config
)

from .scanner import (
    FileScanner,
    IncrementalFileScanner,
    ScanResult,
    ProgressReporter,
    create_file_scanner,
    create_incremental_scanner
)

__all__ = [
    'AppConfig',
    'ScanConfig', 
    'DatabaseConfig',
    'get_config',
    'get_config_manager',
    'reload_config',
    'FileScanner',
    'IncrementalFileScanner',
    'ScanResult',
    'ProgressReporter',
    'create_file_scanner',
    'create_incremental_scanner'
]
