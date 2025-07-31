"""Unity Resource Reference Scanner - Database Core Module

数据库操作核心模块，提供SQLAlchemy会话管理、数据访问层（DAO）、
数据库初始化、迁移和连接池管理等功能。
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Type, TypeVar, Generic
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.pool import StaticPool

from ..core.config import get_config, DatabaseConfig, DatabaseType
from ..models.asset import Base, Asset, AssetType
from ..models.dependency import Dependency, DependencyType, DependencyStrength
from ..models.scan_result import ScanResult, ScanStatus, ScanType

# 类型变量用于泛型DAO
T = TypeVar('T')

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器
    
    负责数据库连接、会话管理、初始化和迁移等核心功能。
    """

    def __init__(self, config: Optional[DatabaseConfig] = None):
        """初始化数据库管理器
        
        Args:
            config: 数据库配置，如果为None则使用全局配置
        """
        self.config = config or get_config().database
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._initialized = False

    @property
    def engine(self) -> Engine:
        """获取数据库引擎"""
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """获取会话工厂"""
        if self._session_factory is None:
            self._session_factory = sessionmaker(bind=self.engine)
        return self._session_factory

    def _create_engine(self) -> Engine:
        """创建数据库引擎"""
        database_url = self._get_database_url()
        
        # SQLite特殊配置
        if self.config.type == DatabaseType.SQLITE:
            engine = create_engine(
                database_url,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30
                },
                echo=False  # 设置为True可以看到SQL语句
            )
            
            # 启用SQLite外键约束
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()
        
        # PostgreSQL配置
        elif self.config.type == DatabaseType.POSTGRESQL:
            engine = create_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=False
            )
        
        # MySQL配置
        elif self.config.type == DatabaseType.MYSQL:
            engine = create_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False
            )
        
        else:
            raise ValueError(f"不支持的数据库类型: {self.config.type}")

        logger.info(f"数据库引擎已创建: {self.config.type.value}")
        return engine

    def _get_database_url(self) -> str:
        """获取数据库连接URL"""
        if self.config.type == DatabaseType.SQLITE:
            db_path = Path(self.config.path)
            # 确保数据库目录存在
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{db_path.absolute()}"
        
        elif self.config.type == DatabaseType.POSTGRESQL:
            # 从配置或环境变量获取PostgreSQL连接信息
            host = os.getenv('DB_HOST', 'localhost')
            port = os.getenv('DB_PORT', '5432')
            database = os.getenv('DB_NAME', 'unity_scanner')
            username = os.getenv('DB_USER', 'postgres')
            password = os.getenv('DB_PASSWORD', '')
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
        
        elif self.config.type == DatabaseType.MYSQL:
            # 从配置或环境变量获取MySQL连接信息
            host = os.getenv('DB_HOST', 'localhost')
            port = os.getenv('DB_PORT', '3306')
            database = os.getenv('DB_NAME', 'unity_scanner')
            username = os.getenv('DB_USER', 'root')
            password = os.getenv('DB_PASSWORD', '')
            return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        
        else:
            raise ValueError(f"不支持的数据库类型: {self.config.type}")

    def initialize_database(self, drop_existing: bool = False) -> None:
        """初始化数据库
        
        Args:
            drop_existing: 是否删除现有表结构
        """
        try:
            if drop_existing:
                logger.warning("删除现有数据库表结构")
                Base.metadata.drop_all(self.engine)
            
            # 创建所有表
            Base.metadata.create_all(self.engine)
            
            # 执行数据库vacuum（仅SQLite）
            if self.config.type == DatabaseType.SQLITE and getattr(self.config, 'vacuum_on_startup', False):
                with self.engine.connect() as conn:
                    conn.execute(text("VACUUM"))
                    logger.info("数据库vacuum操作完成")
            
            self._initialized = True
            logger.info("数据库初始化完成")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    def check_database_health(self) -> Dict[str, Any]:
        """检查数据库健康状态
        
        Returns:
            Dict[str, Any]: 健康状态信息
        """
        health_info = {
            'status': 'unknown',
            'database_type': self.config.type.value,
            'database_path': self.config.path,
            'tables_exist': False,
            'connection_test': False,
            'table_counts': {},
            'error': None
        }
        
        try:
            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                health_info['connection_test'] = True
            
            # 检查表是否存在
            inspector = inspect(self.engine)
            existing_tables = inspector.get_table_names()
            expected_tables = ['assets', 'dependencies', 'scan_results']
            
            health_info['tables_exist'] = all(table in existing_tables for table in expected_tables)
            
            # 获取表记录数量
            if health_info['tables_exist']:
                with self.get_session() as session:
                    health_info['table_counts'] = {
                        'assets': session.query(Asset).count(),
                        'dependencies': session.query(Dependency).count(),
                        'scan_results': session.query(ScanResult).count(),
                    }
            
            # 确定整体状态
            if health_info['connection_test'] and health_info['tables_exist']:
                health_info['status'] = 'healthy'
            else:
                health_info['status'] = 'degraded'
                
        except Exception as e:
            health_info['status'] = 'unhealthy'
            health_info['error'] = str(e)
            logger.error(f"数据库健康检查失败: {e}")
        
        return health_info

    @contextmanager
    def get_session(self):
        """获取数据库会话上下文管理器"""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库会话错误: {e}")
            raise
        finally:
            session.close()

    def backup_database(self, backup_path: Optional[str] = None) -> Optional[str]:
        """备份数据库（仅SQLite）
        
        Args:
            backup_path: 备份文件路径，如果为None则自动生成
            
        Returns:
            Optional[str]: 备份文件路径，失败时返回None
        """
        if self.config.type != DatabaseType.SQLITE:
            logger.warning("数据库备份功能目前仅支持SQLite")
            return None
        
        try:
            import shutil
            
            source_path = Path(self.config.path)
            if not source_path.exists():
                logger.error(f"源数据库文件不存在: {source_path}")
                return None
            
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = str(source_path.parent / f"{source_path.stem}_backup_{timestamp}.db")
            
            shutil.copy2(source_path, backup_path)
            logger.info(f"数据库备份完成: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            return None

    def close(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("数据库连接已关闭")


class BaseDAO(Generic[T]):
    """基础数据访问对象
    
    提供通用的CRUD操作和事务管理功能。
    """

    def __init__(self, model_class: Type[T], db_manager: DatabaseManager):
        """初始化DAO
        
        Args:
            model_class: 数据模型类
            db_manager: 数据库管理器
        """
        self.model_class = model_class
        self.db_manager = db_manager

    def create(self, session: Session, **kwargs) -> T:
        """创建单个记录
        
        Args:
            session: 数据库会话
            **kwargs: 创建参数
            
        Returns:
            T: 创建的记录实例
        """
        instance = self.model_class(**kwargs)
        session.add(instance)
        session.flush()
        return instance

    def create_batch(self, session: Session, records: List[Dict[str, Any]]) -> List[T]:
        """批量创建记录
        
        Args:
            session: 数据库会话
            records: 记录数据列表
            
        Returns:
            List[T]: 创建的记录实例列表
        """
        instances = [self.model_class(**record) for record in records]
        session.add_all(instances)
        session.flush()
        return instances

    def get_by_id(self, session: Session, record_id: Any) -> Optional[T]:
        """根据ID获取记录
        
        Args:
            session: 数据库会话
            record_id: 记录ID
            
        Returns:
            Optional[T]: 记录实例，如果不存在则返回None
        """
        return session.query(self.model_class).get(record_id)

    def get_all(self, session: Session, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """获取所有记录
        
        Args:
            session: 数据库会话
            limit: 限制返回数量
            offset: 偏移量
            
        Returns:
            List[T]: 记录列表
        """
        query = session.query(self.model_class)
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return query.all()

    def update(self, session: Session, record_id: Any, **kwargs) -> Optional[T]:
        """更新记录
        
        Args:
            session: 数据库会话
            record_id: 记录ID
            **kwargs: 更新参数
            
        Returns:
            Optional[T]: 更新后的记录实例
        """
        instance = self.get_by_id(session, record_id)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            session.flush()
        return instance

    def delete(self, session: Session, record_id: Any) -> bool:
        """删除记录
        
        Args:
            session: 数据库会话
            record_id: 记录ID
            
        Returns:
            bool: 是否删除成功
        """
        instance = self.get_by_id(session, record_id)
        if instance:
            session.delete(instance)
            session.flush()
            return True
        return False

    def count(self, session: Session) -> int:
        """获取记录总数
        
        Args:
            session: 数据库会话
            
        Returns:
            int: 记录总数
        """
        return session.query(self.model_class).count()


class AssetDAO(BaseDAO[Asset]):
    """资源数据访问对象"""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(Asset, db_manager)

    def get_by_guid(self, session: Session, guid: str) -> Optional[Asset]:
        """根据GUID获取资源
        
        Args:
            session: 数据库会话
            guid: 资源GUID
            
        Returns:
            Optional[Asset]: 资源实例
        """
        return session.query(Asset).filter(Asset.guid == guid).first()

    def get_by_path(self, session: Session, file_path: str) -> Optional[Asset]:
        """根据文件路径获取资源
        
        Args:
            session: 数据库会话
            file_path: 文件路径
            
        Returns:
            Optional[Asset]: 资源实例
        """
        return session.query(Asset).filter(Asset.file_path == file_path).first()

    def get_by_type(self, session: Session, asset_type: AssetType, active_only: bool = True) -> List[Asset]:
        """根据资源类型获取资源列表
        
        Args:
            session: 数据库会话
            asset_type: 资源类型
            active_only: 是否只返回活跃资源
            
        Returns:
            List[Asset]: 资源列表
        """
        query = session.query(Asset).filter(Asset.asset_type == asset_type.value)
        if active_only:
            query = query.filter(Asset.is_active == True)
        return query.all()

    def get_inactive_assets(self, session: Session) -> List[Asset]:
        """获取非活跃资源列表
        
        Args:
            session: 数据库会话
            
        Returns:
            List[Asset]: 非活跃资源列表
        """
        return session.query(Asset).filter(Asset.is_active == False).all()

    def get_unanalyzed_assets(self, session: Session) -> List[Asset]:
        """获取未分析的资源列表
        
        Args:
            session: 数据库会话
            
        Returns:
            List[Asset]: 未分析资源列表
        """
        return session.query(Asset).filter(
            Asset.is_active == True,
            Asset.is_analyzed == False
        ).all()

    def update_or_create(self, session: Session, guid: str, **kwargs) -> Asset:
        """更新或创建资源
        
        Args:
            session: 数据库会话
            guid: 资源GUID
            **kwargs: 资源属性
            
        Returns:
            Asset: 资源实例
        """
        asset = self.get_by_guid(session, guid)
        if asset:
            # 更新现有资源
            for key, value in kwargs.items():
                if hasattr(asset, key):
                    setattr(asset, key, value)
            asset.updated_at = datetime.utcnow()
        else:
            # 创建新资源
            asset = Asset(guid=guid, **kwargs)
            session.add(asset)
        
        session.flush()
        return asset


class DependencyDAO(BaseDAO[Dependency]):
    """依赖关系数据访问对象"""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(Dependency, db_manager)

    def get_by_source_guid(self, session: Session, source_guid: str, active_only: bool = True) -> List[Dependency]:
        """根据源GUID获取依赖关系列表
        
        Args:
            session: 数据库会话
            source_guid: 源资源GUID
            active_only: 是否只返回活跃依赖
            
        Returns:
            List[Dependency]: 依赖关系列表
        """
        query = session.query(Dependency).filter(Dependency.source_guid == source_guid)
        if active_only:
            query = query.filter(Dependency.is_active == True)
        return query.all()

    def get_by_target_guid(self, session: Session, target_guid: str, active_only: bool = True) -> List[Dependency]:
        """根据目标GUID获取依赖关系列表
        
        Args:
            session: 数据库会话
            target_guid: 目标资源GUID
            active_only: 是否只返回活跃依赖
            
        Returns:
            List[Dependency]: 依赖关系列表
        """
        query = session.query(Dependency).filter(Dependency.target_guid == target_guid)
        if active_only:
            query = query.filter(Dependency.is_active == True)
        return query.all()

    def get_by_type(self, session: Session, dependency_type: DependencyType, active_only: bool = True) -> List[Dependency]:
        """根据依赖类型获取依赖关系列表
        
        Args:
            session: 数据库会话
            dependency_type: 依赖类型
            active_only: 是否只返回活跃依赖
            
        Returns:
            List[Dependency]: 依赖关系列表
        """
        query = session.query(Dependency).filter(Dependency.dependency_type == dependency_type.value)
        if active_only:
            query = query.filter(Dependency.is_active == True)
        return query.all()

    def create_or_update_dependency(
        self, 
        session: Session,
        source_guid: str,
        target_guid: str,
        dependency_type: DependencyType,
        **kwargs
    ) -> Dependency:
        """创建或更新依赖关系
        
        Args:
            session: 数据库会话
            source_guid: 源资源GUID
            target_guid: 目标资源GUID
            dependency_type: 依赖类型
            **kwargs: 其他属性
            
        Returns:
            Dependency: 依赖关系实例
        """
        # 检查是否已存在相同的依赖关系
        context_path = kwargs.get('context_path', None)
        existing = session.query(Dependency).filter(
            Dependency.source_guid == source_guid,
            Dependency.target_guid == target_guid,
            Dependency.dependency_type == dependency_type.value,
            Dependency.context_path == context_path
        ).first()
        
        if existing:
            # 更新现有依赖关系
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            existing.is_active = True
            dependency = existing
        else:
            # 创建新依赖关系
            dependency = Dependency.create_dependency(
                source_guid=source_guid,
                target_guid=target_guid,
                dependency_type=dependency_type,
                **kwargs
            )
            session.add(dependency)
        
        session.flush()
        return dependency


class ScanResultDAO(BaseDAO[ScanResult]):
    """扫描结果数据访问对象"""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(ScanResult, db_manager)

    def get_by_scan_id(self, session: Session, scan_id: str) -> Optional[ScanResult]:
        """根据扫描ID获取扫描结果
        
        Args:
            session: 数据库会话
            scan_id: 扫描ID
            
        Returns:
            Optional[ScanResult]: 扫描结果实例
        """
        return session.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()

    def get_recent_scans(self, session: Session, limit: int = 10) -> List[ScanResult]:
        """获取最近的扫描结果
        
        Args:
            session: 数据库会话
            limit: 限制返回数量
            
        Returns:
            List[ScanResult]: 扫描结果列表
        """
        return session.query(ScanResult).order_by(
            ScanResult.started_at.desc()
        ).limit(limit).all()

    def get_successful_scans(self, session: Session, limit: Optional[int] = None) -> List[ScanResult]:
        """获取成功的扫描结果
        
        Args:
            session: 数据库会话
            limit: 限制返回数量
            
        Returns:
            List[ScanResult]: 成功的扫描结果列表
        """
        query = session.query(ScanResult).filter(
            ScanResult.scan_status == ScanStatus.COMPLETED.value
        ).order_by(ScanResult.completed_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()

    def cleanup_old_scans(self, session: Session, keep_days: int = 30) -> int:
        """清理旧的扫描记录
        
        Args:
            session: 数据库会话
            keep_days: 保留天数
            
        Returns:
            int: 删除的记录数量
        """
        cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
        
        deleted_count = session.query(ScanResult).filter(
            ScanResult.started_at < cutoff_date,
            ScanResult.scan_status.in_([
                ScanStatus.COMPLETED.value,
                ScanStatus.FAILED.value,
                ScanStatus.CANCELLED.value
            ])
        ).delete()
        
        session.flush()
        return deleted_count


# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def initialize_database(drop_existing: bool = False) -> None:
    """初始化数据库
    
    Args:
        drop_existing: 是否删除现有表结构
    """
    db_manager = get_database_manager()
    db_manager.initialize_database(drop_existing=drop_existing)


def get_session():
    """获取数据库会话上下文管理器"""
    db_manager = get_database_manager()
    return db_manager.get_session()


# DAO实例工厂函数
def get_asset_dao() -> AssetDAO:
    """获取资源数据访问对象"""
    return AssetDAO(get_database_manager())


def get_dependency_dao() -> DependencyDAO:
    """获取依赖关系数据访问对象"""
    return DependencyDAO(get_database_manager())


def get_scan_result_dao() -> ScanResultDAO:
    """获取扫描结果数据访问对象"""
    return ScanResultDAO(get_database_manager())
