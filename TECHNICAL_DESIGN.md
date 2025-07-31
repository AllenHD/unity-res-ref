# Unity 资源引用扫描工具 - 技术设计文档

## 文档信息
- **创建日期**: 2025年7月31日
- **版本**: v1.0
- **作者**: GitHub Copilot
- **项目**: unity-res-ref

## 目录
1. [项目概述](#项目概述)
2. [需求分析](#需求分析)
3. [Unity资源管理机制研究](#unity资源管理机制研究)
4. [技术架构设计](#技术架构设计)
5. [数据库设计](#数据库设计)
6. [核心功能实现](#核心功能实现)
7. [性能优化策略](#性能优化策略)
8. [用户界面设计](#用户界面设计)
9. [实施计划](#实施计划)
10. [技术风险分析](#技术风险分析)

## 项目概述

### 背景
开发一个Python工具来扫描Unity项目的资源引用情况，主要通过解析.meta文件来分析资源依赖关系。由于工程规模大、文件数量多，需要支持配置化扫描路径、排除路径，并使用数据库缓存实现增量扫描功能。

### 目标
- 构建完整的Unity项目资源依赖关系图
- 支持大型项目的高效扫描
- 提供增量扫描功能，减少重复工作
- 支持灵活的配置管理
- 提供多种查询和导出功能

## 需求分析

### 功能需求
1. **资源扫描**
   - 扫描Unity项目中的所有资源文件
   - 解析.meta文件获取GUID信息
   - 分析资源间的引用关系

2. **配置管理**
   - 支持配置扫描路径
   - 支持配置排除路径
   - 灵活的文件类型过滤

3. **增量扫描**
   - 检测文件变更
   - 只处理修改过的文件
   - 维护扫描历史记录

4. **数据持久化**
   - 使用数据库缓存依赖关系
   - 支持快速查询
   - 数据完整性保证

5. **查询功能**
   - 查找资源依赖
   - 查找资源被引用情况
   - 检测未使用资源
   - 检测循环依赖

### 非功能需求
1. **性能要求**
   - 支持大型项目（10万+文件）
   - 扫描时间控制在合理范围内
   - 内存使用优化

2. **可用性要求**
   - 简洁的命令行接口
   - 清晰的错误信息
   - 详细的进度显示

3. **扩展性要求**
   - 模块化设计
   - 插件化架构
   - API接口支持

## Unity资源管理机制研究

### Unity资源标识系统

基于对Unity文档和源码的研究，Unity使用以下机制管理资源：

#### GUID系统
- 每个资源都有唯一的32位十六进制GUID
- GUID存储在对应的.meta文件中
- 用于建立资源间的引用关系

#### FileID系统
- 资源内部对象使用fileID进行标识
- 不同类型的组件有不同的fileID
- 与GUID配合使用定位具体对象

#### Meta文件结构
```yaml
fileFormatVersion: 2
guid: 1234567890abcdef1234567890abcdef
TextureImporter:
  # 导入设置...
```

#### 资源引用格式
```yaml
# Unity资源文件中的引用格式
m_Material: {fileID: 2100000, guid: 1234567890abcdef1234567890abcdef, type: 2}
```

### Unity文件类型分析

1. **.prefab文件** - 预制体，YAML格式，包含组件引用
2. **.scene文件** - 场景文件，YAML格式，包含对象引用
3. **.asset文件** - ScriptableObject等自定义资源
4. **.mat文件** - 材质文件，包含shader和贴图引用
5. **.controller文件** - 动画控制器
6. **.anim文件** - 动画剪辑

## 技术架构设计

### 整体架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   配置管理模块   │────│   文件扫描模块   │────│   解析器模块     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   数据库模块     │◄───│   依赖图构建     │◄───│   缓存管理模块   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   查询接口模块   │────│   命令行接口     │────│   导出模块       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 项目结构

```
unity-res-ref/
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # 数据库操作
│   │   ├── scanner.py         # 核心扫描逻辑
│   │   └── dependency_graph.py # 依赖图构建
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base_parser.py     # 解析器基类
│   │   ├── meta_parser.py     # .meta文件解析
│   │   ├── prefab_parser.py   # .prefab文件解析
│   │   ├── scene_parser.py    # .scene文件解析
│   │   ├── material_parser.py # .mat文件解析
│   │   └── asset_parser.py    # 通用asset解析
│   ├── models/
│   │   ├── __init__.py
│   │   ├── asset.py           # 资源数据模型
│   │   ├── dependency.py     # 依赖关系模型
│   │   └── scan_result.py    # 扫描结果模型
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── file_watcher.py    # 文件变更监控
│   │   ├── yaml_utils.py      # YAML处理工具
│   │   ├── path_utils.py      # 路径处理工具
│   │   └── performance.py    # 性能监控工具
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── commands.py        # 命令行接口
│   │   └── formatters.py      # 输出格式化
│   └── api/
│       ├── __init__.py
│       └── rest_api.py        # REST API接口
├── config/
│   ├── default.yaml           # 默认配置
│   └── schema.json           # 配置验证schema
├── tests/
│   ├── unit/                 # 单元测试
│   ├── integration/          # 集成测试
│   └── fixtures/             # 测试数据
├── docs/
│   ├── api.md               # API文档
│   ├── user_guide.md        # 用户指南
│   └── developer_guide.md   # 开发者指南
├── pyproject.toml
├── README.md
└── TECHNICAL_DESIGN.md      # 本文档
```

### 技术栈选择

```toml
[project]
name = "unity-res-ref"
version = "0.1.0"
description = "Unity project resource reference scanner"
requires-python = ">=3.11"

dependencies = [
    "ruamel.yaml>=0.18.0",      # 保持格式的YAML解析
    "sqlalchemy>=2.0.0",        # ORM数据库操作
    "click>=8.1.0",             # 命令行界面框架
    "watchdog>=3.0.0",          # 文件系统监控
    "pydantic>=2.0.0",          # 数据验证和序列化
    "rich>=13.0.0",             # 命令行美化输出
    "typer>=0.9.0",             # 现代CLI框架
    "asyncio-extensions>=1.0.0", # 异步I/O扩展
    "networkx>=3.0",            # 图算法库
    "fastapi>=0.100.0",         # Web API框架(可选)
    "uvicorn>=0.23.0",          # ASGI服务器(可选)
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "mypy>=1.0.0",
    "ruff>=0.0.280",
]
```

## 数据库设计

### 数据库Schema

```sql
-- 资源表：存储所有资源的基本信息
CREATE TABLE assets (
    guid VARCHAR(32) PRIMARY KEY,           -- Unity资源GUID
    file_path TEXT NOT NULL,                -- 文件相对路径
    file_type VARCHAR(20),                  -- 文件类型(.prefab, .scene等)
    file_size INTEGER,                     -- 文件大小(字节)
    last_modified TIMESTAMP,               -- 最后修改时间
    last_scanned TIMESTAMP,                -- 最后扫描时间
    checksum VARCHAR(64),                  -- 文件校验和
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 依赖关系表：存储资源间的引用关系
CREATE TABLE dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_guid VARCHAR(32) NOT NULL,      -- 引用源资源GUID
    target_guid VARCHAR(32) NOT NULL,      -- 被引用资源GUID
    file_id INTEGER,                       -- Unity FileID
    reference_type VARCHAR(50),            -- 引用类型(material, texture, script等)
    property_path TEXT,                    -- 属性路径
    line_number INTEGER,                   -- 文件中的行号
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_guid) REFERENCES assets(guid) ON DELETE CASCADE,
    FOREIGN KEY (target_guid) REFERENCES assets(guid) ON DELETE CASCADE
);

-- 扫描日志表：记录扫描历史
CREATE TABLE scan_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_type VARCHAR(20),                 -- 扫描类型(full, incremental)
    scan_start TIMESTAMP,                  -- 扫描开始时间
    scan_end TIMESTAMP,                    -- 扫描结束时间
    files_scanned INTEGER DEFAULT 0,      -- 扫描文件数
    files_added INTEGER DEFAULT 0,        -- 新增文件数
    files_updated INTEGER DEFAULT 0,      -- 更新文件数
    files_deleted INTEGER DEFAULT 0,      -- 删除文件数
    dependencies_found INTEGER DEFAULT 0,  -- 发现依赖数
    errors INTEGER DEFAULT 0,             -- 错误数
    error_details TEXT,                   -- 错误详情
    config_snapshot TEXT,                 -- 配置快照
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 配置表：存储项目配置
CREATE TABLE project_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引优化
CREATE INDEX idx_dependencies_source ON dependencies(source_guid);
CREATE INDEX idx_dependencies_target ON dependencies(target_guid);
CREATE INDEX idx_assets_path ON assets(file_path);
CREATE INDEX idx_assets_type ON assets(file_type);
CREATE INDEX idx_assets_modified ON assets(last_modified);
CREATE INDEX idx_scan_logs_date ON scan_logs(scan_start);
```

### 数据模型

```python
# models/asset.py
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

Base = declarative_base()

class Asset(Base):
    __tablename__ = 'assets'
    
    guid = Column(String(32), primary_key=True)
    file_path = Column(Text, nullable=False)
    file_type = Column(String(20))
    file_size = Column(Integer)
    last_modified = Column(DateTime)
    last_scanned = Column(DateTime)
    checksum = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class AssetModel(BaseModel):
    """Pydantic模型用于数据验证"""
    guid: str
    file_path: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    last_modified: Optional[datetime] = None
    dependencies: Optional[List['DependencyModel']] = []
    
    class Config:
        from_attributes = True
```

## 核心功能实现

### 配置管理系统

```yaml
# config/default.yaml
project:
  name: "Unity Project Scanner"
  unity_project_path: ""                   # Unity项目根路径
  unity_version: ""                        # Unity版本(自动检测)

scan:
  paths:                                   # 扫描路径
    - "Assets/"
    - "Packages/"
  exclude_paths:                          # 排除路径
    - "Assets/StreamingAssets/"
    - "Assets/Plugins/Android/"
    - "Assets/Plugins/iOS/"
    - "Library/"
    - "Temp/"
    - "Build/"
  file_extensions:                        # 扫描的文件类型
    - ".prefab"
    - ".scene"
    - ".asset"
    - ".mat"
    - ".controller"
    - ".anim"
    - ".cs"                             # C#脚本(分析ScriptableObject)
  max_file_size_mb: 50                   # 最大文件大小限制
  ignore_hidden_files: true             # 忽略隐藏文件

database:
  type: "sqlite"                         # 数据库类型
  path: "./unity_deps.db"               # 数据库路径
  backup_enabled: true                  # 是否自动备份
  backup_interval_hours: 24             # 备份间隔
  vacuum_on_startup: false              # 启动时是否压缩数据库

performance:
  max_workers: 4                        # 最大工作线程数
  batch_size: 100                       # 批处理大小
  memory_limit_mb: 512                  # 内存使用限制
  enable_async_io: true                 # 启用异步I/O
  cache_size_mb: 128                    # 解析缓存大小

output:
  verbosity: "info"                     # 日志级别
  progress_bar: true                    # 显示进度条
  color_output: true                    # 彩色输出
  export_formats: ["json", "csv", "dot"] # 支持的导出格式

features:
  detect_unused_assets: true            # 检测未使用资源
  detect_circular_deps: true            # 检测循环依赖
  generate_reports: true                # 生成报告
  web_interface: false                  # Web界面(可选)
```

### 核心扫描算法

```python
# core/scanner.py
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ScanResult:
    """扫描结果"""
    files_scanned: int = 0
    dependencies_found: int = 0
    errors: List[str] = None
    duration: float = 0.0
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class UnityProjectScanner:
    """Unity项目扫描器"""
    
    def __init__(self, config, database, parser_factory):
        self.config = config
        self.database = database
        self.parser_factory = parser_factory
        self.logger = logging.getLogger(__name__)
        
    async def scan_project(self, incremental: bool = True) -> ScanResult:
        """扫描项目"""
        start_time = datetime.utcnow()
        result = ScanResult()
        
        try:
            # 1. 构建GUID映射表
            self.logger.info("Building GUID mapping...")
            guid_map = await self._build_guid_mapping()
            
            # 2. 获取需要扫描的文件
            if incremental:
                files_to_scan = await self._get_changed_files()
            else:
                files_to_scan = await self._get_all_scannable_files()
            
            self.logger.info(f"Found {len(files_to_scan)} files to scan")
            
            # 3. 并行扫描文件
            dependencies = await self._scan_files_parallel(files_to_scan, guid_map)
            
            # 4. 更新数据库
            await self._update_database(dependencies)
            
            # 5. 构建依赖图索引
            await self._build_dependency_index()
            
            result.files_scanned = len(files_to_scan)
            result.dependencies_found = len(dependencies)
            result.duration = (datetime.utcnow() - start_time).total_seconds()
            
        except Exception as e:
            self.logger.error(f"Scan failed: {e}")
            result.errors.append(str(e))
            
        return result
    
    async def _build_guid_mapping(self) -> Dict[str, str]:
        """构建GUID到文件路径的映射"""
        guid_map = {}
        meta_files = self._find_meta_files()
        
        with ThreadPoolExecutor(max_workers=self.config.performance.max_workers) as executor:
            tasks = []
            for meta_file in meta_files:
                task = executor.submit(self._parse_meta_file, meta_file)
                tasks.append((meta_file, task))
            
            for meta_file, task in tasks:
                try:
                    guid = task.result()
                    if guid:
                        asset_path = str(meta_file)[:-5]  # 移除.meta后缀
                        guid_map[guid] = asset_path
                except Exception as e:
                    self.logger.warning(f"Failed to parse {meta_file}: {e}")
        
        return guid_map
    
    async def _scan_files_parallel(self, files: List[Path], guid_map: Dict[str, str]) -> List[Dict]:
        """并行扫描文件"""
        dependencies = []
        batch_size = self.config.performance.batch_size
        
        # 分批处理文件
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            batch_deps = await self._process_file_batch(batch, guid_map)
            dependencies.extend(batch_deps)
            
            # 进度报告
            progress = min(i + batch_size, len(files))
            self.logger.info(f"Processed {progress}/{len(files)} files")
        
        return dependencies
    
    async def _process_file_batch(self, files: List[Path], guid_map: Dict[str, str]) -> List[Dict]:
        """处理文件批次"""
        with ThreadPoolExecutor(max_workers=self.config.performance.max_workers) as executor:
            tasks = []
            for file_path in files:
                parser = self.parser_factory.get_parser(file_path)
                if parser:
                    task = executor.submit(parser.parse, file_path, guid_map)
                    tasks.append(task)
            
            dependencies = []
            for task in tasks:
                try:
                    file_deps = task.result()
                    dependencies.extend(file_deps)
                except Exception as e:
                    self.logger.warning(f"Parse error: {e}")
            
            return dependencies
```

### 文件解析器架构

```python
# parsers/base_parser.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pathlib import Path
import re

class Reference:
    """资源引用"""
    def __init__(self, target_guid: str, file_id: int = 0, 
                 ref_type: str = "", property_path: str = ""):
        self.target_guid = target_guid
        self.file_id = file_id
        self.ref_type = ref_type
        self.property_path = property_path

class BaseParser(ABC):
    """解析器基类"""
    
    # Unity GUID引用的正则表达式
    GUID_PATTERN = re.compile(
        r'fileID:\s*(-?\d+),\s*guid:\s*([a-f0-9]{32}),\s*type:\s*(\d+)'
    )
    
    # 简化的GUID引用模式
    SIMPLE_GUID_PATTERN = re.compile(r'guid:\s*([a-f0-9]{32})')
    
    @abstractmethod
    def parse(self, file_path: Path, guid_map: Dict[str, str]) -> List[Dict]:
        """解析文件，返回依赖关系列表"""
        pass
    
    def extract_guid_references(self, content: str) -> List[Reference]:
        """从文件内容中提取GUID引用"""
        references = []
        
        # 提取完整的引用信息
        for match in self.GUID_PATTERN.finditer(content):
            file_id, guid, type_id = match.groups()
            references.append(Reference(
                target_guid=guid,
                file_id=int(file_id),
                ref_type=f"type_{type_id}"
            ))
        
        # 提取简单的GUID引用
        for match in self.SIMPLE_GUID_PATTERN.finditer(content):
            guid = match.group(1)
            if not any(ref.target_guid == guid for ref in references):
                references.append(Reference(target_guid=guid))
        
        return references
    
    def is_valid_guid(self, guid: str) -> bool:
        """验证GUID格式"""
        return bool(re.match(r'^[a-f0-9]{32}$', guid))

# parsers/prefab_parser.py
class PrefabParser(BaseParser):
    """预制体文件解析器"""
    
    def parse(self, file_path: Path, guid_map: Dict[str, str]) -> List[Dict]:
        """解析预制体文件"""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            source_guid = self._get_asset_guid(file_path, guid_map)
            if not source_guid:
                return []
            
            references = self.extract_guid_references(content)
            
            for ref in references:
                if ref.target_guid in guid_map:
                    dependencies.append({
                        'source_guid': source_guid,
                        'target_guid': ref.target_guid,
                        'file_id': ref.file_id,
                        'reference_type': 'prefab_reference',
                        'property_path': ref.property_path
                    })
                    
        except Exception as e:
            logging.warning(f"Failed to parse prefab {file_path}: {e}")
        
        return dependencies
    
    def _get_asset_guid(self, file_path: Path, guid_map: Dict[str, str]) -> Optional[str]:
        """获取资源的GUID"""
        for guid, path in guid_map.items():
            if Path(path) == file_path:
                return guid
        return None
```

## 性能优化策略

### 1. 并发处理优化

```python
# utils/performance.py
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import List, Callable, Any
import psutil
import gc

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self, config):
        self.config = config
        self.memory_limit = config.performance.memory_limit_mb * 1024 * 1024
        
    async def parallel_process(self, items: List[Any], 
                             processor: Callable, 
                             max_workers: int = None) -> List[Any]:
        """并行处理项目列表"""
        if max_workers is None:
            max_workers = self.config.performance.max_workers
            
        # 根据系统资源调整工作线程数
        cpu_count = psutil.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # 动态调整线程数
        optimal_workers = min(max_workers, cpu_count, int(memory_gb))
        
        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            tasks = [executor.submit(processor, item) for item in items]
            results = []
            
            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                    results.append(result)
                    
                    # 内存监控
                    if self._check_memory_usage():
                        gc.collect()  # 触发垃圾回收
                        
                except Exception as e:
                    logging.warning(f"Task failed: {e}")
                    
        return results
    
    def _check_memory_usage(self) -> bool:
        """检查内存使用情况"""
        process = psutil.Process()
        memory_usage = process.memory_info().rss
        return memory_usage > self.memory_limit
    
    @contextmanager
    def performance_monitor(self, operation_name: str):
        """性能监控上下文管理器"""
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss
        
        try:
            yield
        finally:
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss
            
            duration = end_time - start_time
            memory_delta = end_memory - start_memory
            
            logging.info(f"{operation_name}: {duration:.2f}s, "
                        f"Memory: {memory_delta/1024/1024:.1f}MB")
```

### 2. 增量扫描实现

```python
# core/incremental_scanner.py
from typing import Set, List
from pathlib import Path
from datetime import datetime
import hashlib

class IncrementalScanner:
    """增量扫描器"""
    
    def __init__(self, database, config):
        self.database = database
        self.config = config
    
    async def get_changed_files(self) -> List[Path]:
        """获取变更的文件列表"""
        changed_files = []
        last_scan_time = await self._get_last_scan_time()
        
        for scan_path in self.config.scan.paths:
            path = Path(scan_path)
            if path.exists():
                changed_files.extend(
                    await self._scan_directory_changes(path, last_scan_time)
                )
        
        return changed_files
    
    async def _scan_directory_changes(self, directory: Path, 
                                    last_scan_time: datetime) -> List[Path]:
        """扫描目录变更"""
        changed_files = []
        
        for file_path in directory.rglob('*'):
            if self._should_scan_file(file_path):
                if await self._is_file_changed(file_path, last_scan_time):
                    changed_files.append(file_path)
        
        return changed_files
    
    async def _is_file_changed(self, file_path: Path, 
                             last_scan_time: datetime) -> bool:
        """检查文件是否已变更"""
        try:
            # 检查修改时间
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime > last_scan_time:
                return True
            
            # 检查文件校验和
            current_checksum = await self._calculate_checksum(file_path)
            stored_checksum = await self.database.get_file_checksum(str(file_path))
            
            return current_checksum != stored_checksum
            
        except Exception:
            return True  # 如果无法确定，则认为已变更
    
    async def _calculate_checksum(self, file_path: Path) -> str:
        """计算文件校验和"""
        hash_md5 = hashlib.md5()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()
```

### 3. 内存优化

```python
# utils/memory_optimizer.py
import gc
import weakref
from typing import Generator, Any
import mmap

class MemoryOptimizer:
    """内存优化器"""
    
    @staticmethod
    def stream_large_file(file_path: Path, chunk_size: int = 8192) -> Generator[str, None, None]:
        """流式读取大文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    
    @staticmethod
    def memory_mapped_file(file_path: Path) -> mmap.mmap:
        """内存映射文件"""
        with open(file_path, 'rb') as f:
            return mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    
    @staticmethod
    def batch_processor(items: List[Any], batch_size: int) -> Generator[List[Any], None, None]:
        """批量处理器"""
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            yield batch
            
            # 强制垃圾回收
            if i % (batch_size * 10) == 0:
                gc.collect()
    
    class ObjectPool:
        """对象池"""
        def __init__(self, factory, max_size=100):
            self.factory = factory
            self.pool = []
            self.max_size = max_size
        
        def get(self):
            if self.pool:
                return self.pool.pop()
            return self.factory()
        
        def release(self, obj):
            if len(self.pool) < self.max_size:
                # 重置对象状态
                if hasattr(obj, 'reset'):
                    obj.reset()
                self.pool.append(obj)
```

## 用户界面设计

### 命令行接口

```python
# cli/commands.py
import click
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from typing import Optional

app = typer.Typer(help="Unity Resource Reference Scanner")
console = Console()

@app.command()
def init(
    project_path: str = typer.Argument(..., help="Unity project path"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path")
):
    """Initialize project configuration"""
    console.print(f"[green]Initializing project at: {project_path}[/green]")
    # 实现初始化逻辑
    
@app.command()
def scan(
    full: bool = typer.Option(False, "--full", "-f", help="Full scan"),
    incremental: bool = typer.Option(True, "--incremental", "-i", help="Incremental scan"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file")
):
    """Scan Unity project for asset references"""
    scan_type = "full" if full else "incremental"
    
    with Progress() as progress:
        task = progress.add_task(f"[cyan]Running {scan_type} scan...", total=100)
        
        # 实现扫描逻辑
        # progress.update(task, advance=10)
        
    console.print("[green]Scan completed successfully![/green]")

@app.command("find-deps")
def find_dependencies(
    asset_path: str = typer.Argument(..., help="Asset path to analyze"),
    depth: int = typer.Option(1, "--depth", "-d", help="Dependency depth"),
    format: str = typer.Option("table", "--format", "-f", help="Output format")
):
    """Find asset dependencies"""
    console.print(f"[cyan]Finding dependencies for: {asset_path}[/cyan]")
    
    # 创建结果表格
    table = Table(title="Asset Dependencies")
    table.add_column("Asset Path", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Reference Type", style="green")
    
    # 添加示例数据
    table.add_row("Assets/Materials/Player.mat", "Material", "Direct")
    table.add_row("Assets/Textures/player_diffuse.png", "Texture2D", "Material Property")
    
    console.print(table)

@app.command("find-usage")
def find_asset_usage(
    asset_path: str = typer.Argument(..., help="Asset path to analyze"),
    include_indirect: bool = typer.Option(False, "--indirect", help="Include indirect references")
):
    """Find where an asset is used"""
    console.print(f"[cyan]Finding usage for: {asset_path}[/cyan]")
    
@app.command("find-unused")
def find_unused_assets(
    exclude_patterns: Optional[List[str]] = typer.Option(None, "--exclude", help="Exclude patterns")
):
    """Find unused assets"""
    console.print("[cyan]Scanning for unused assets...[/cyan]")
    
@app.command("find-circular")
def find_circular_dependencies():
    """Find circular dependencies"""
    console.print("[cyan]Scanning for circular dependencies...[/cyan]")

@app.command()
def export(
    format: str = typer.Option("json", "--format", "-f", help="Export format (json, csv, dot)"),
    output: str = typer.Option("dependencies", "--output", "-o", help="Output file prefix"),
    filter_types: Optional[List[str]] = typer.Option(None, "--filter", help="Filter by asset types")
):
    """Export dependency data"""
    output_file = f"{output}.{format}"
    console.print(f"[green]Exporting to: {output_file}[/green]")

@app.command()
def serve(
    port: int = typer.Option(8080, "--port", "-p", help="Server port"),
    host: str = typer.Option("localhost", "--host", "-h", help="Server host")
):
    """Start web interface server"""
    console.print(f"[green]Starting server at http://{host}:{port}[/green]")
    # 启动Web服务器

@app.command()
def stats():
    """Show project statistics"""
    table = Table(title="Project Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Assets", "1,234")
    table.add_row("Dependencies", "5,678")
    table.add_row("Unused Assets", "42")
    table.add_row("Circular Dependencies", "3")
    
    console.print(table)

if __name__ == "__main__":
    app()
```

### 配置验证

```python
# core/config.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from pathlib import Path
import yaml

class ScanConfig(BaseModel):
    paths: List[str] = Field(default_factory=lambda: ["Assets/"])
    exclude_paths: List[str] = Field(default_factory=list)
    file_extensions: List[str] = Field(default_factory=lambda: [".prefab", ".scene"])
    max_file_size_mb: int = Field(default=50, ge=1, le=1000)
    ignore_hidden_files: bool = True

class DatabaseConfig(BaseModel):
    type: str = Field(default="sqlite")
    path: str = Field(default="./unity_deps.db")
    backup_enabled: bool = True
    backup_interval_hours: int = Field(default=24, ge=1)

class PerformanceConfig(BaseModel):
    max_workers: int = Field(default=4, ge=1, le=32)
    batch_size: int = Field(default=100, ge=1)
    memory_limit_mb: int = Field(default=512, ge=128)
    enable_async_io: bool = True
    cache_size_mb: int = Field(default=128, ge=32)

class ProjectConfig(BaseModel):
    name: str = "Unity Project Scanner"
    unity_project_path: str = ""
    unity_version: Optional[str] = None

class OutputConfig(BaseModel):
    verbosity: str = Field(default="info")
    progress_bar: bool = True
    color_output: bool = True
    export_formats: List[str] = Field(default_factory=lambda: ["json", "csv"])

class Config(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    
    @validator('project')
    def validate_unity_project_path(cls, v):
        if v.unity_project_path and not Path(v.unity_project_path).exists():
            raise ValueError(f"Unity project path does not exist: {v.unity_project_path}")
        return v
    
    @classmethod
    def load_from_file(cls, config_path: str) -> 'Config':
        """从文件加载配置"""
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    def save_to_file(self, config_path: str):
        """保存配置到文件"""
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.dict(), f, default_flow_style=False)
```

## 实施计划

### 开发阶段规划

#### 阶段一：基础架构（2周）
**目标**：建立项目基础架构和核心组件

**任务清单**：
- [ ] 项目结构搭建
- [ ] 配置管理系统实现
- [ ] 数据库模型设计和实现
- [ ] 基础解析器框架
- [ ] Meta文件解析器实现
- [ ] 单元测试框架搭建

**交付物**：
- 完整的项目结构
- 配置文件和验证系统
- SQLite数据库支持
- Meta文件解析功能
- 基础测试用例

#### 阶段二：核心扫描功能（2周）
**目标**：实现基本的资源扫描和依赖分析功能

**任务清单**：
- [ ] 文件系统扫描器实现
- [ ] Prefab文件解析器
- [ ] Scene文件解析器
- [ ] Material文件解析器
- [ ] 依赖关系构建器
- [ ] 基本查询功能

**交付物**：
- 完整的文件扫描功能
- 多种资源类型解析支持
- 依赖关系数据库存储
- 基本的依赖查询功能

#### 阶段三：增量扫描和性能优化（1.5周）
**目标**：实现增量扫描和性能优化

**任务清单**：
- [ ] 文件变更检测机制
- [ ] 增量扫描逻辑
- [ ] 并发处理优化
- [ ] 内存使用优化
- [ ] 缓存机制实现
- [ ] 性能监控工具

**交付物**：
- 增量扫描功能
- 多线程/异步处理
- 内存优化机制
- 性能监控报告

#### 阶段四：命令行界面完善（1周）
**目标**：完善用户界面和交互体验

**任务清单**：
- [ ] Click/Typer命令行框架集成
- [ ] Rich输出美化
- [ ] 进度条和状态显示
- [ ] 错误处理和用户提示
- [ ] 配置文件生成和管理
- [ ] 帮助文档完善

**交付物**：
- 完整的CLI工具
- 用户友好的输出界面
- 详细的帮助文档

#### 阶段五：高级功能和导出（1周）
**目标**：实现高级分析功能和数据导出

**任务清单**：
- [ ] 未使用资源检测
- [ ] 循环依赖检测
- [ ] 依赖图可视化
- [ ] 多格式数据导出(JSON, CSV, DOT)
- [ ] HTML报告生成
- [ ] 统计分析功能

**交付物**：
- 高级分析功能
- 多种导出格式支持
- 可视化报告

#### 阶段六：测试和优化（1周）
**目标**：全面测试和性能调优

**任务清单**：
- [ ] 单元测试完善
- [ ] 集成测试实现
- [ ] 大型项目性能测试
- [ ] 内存泄漏检测
- [ ] 错误处理测试
- [ ] 跨平台兼容性测试

**交付物**：
- 完整的测试套件
- 性能基准测试
- 稳定性验证报告

#### 阶段七：文档和发布准备（0.5周）
**目标**：完善文档和发布准备

**任务清单**：
- [ ] API文档生成
- [ ] 用户使用手册
- [ ] 开发者指南
- [ ] 性能调优指南
- [ ] PyPI打包配置
- [ ] Docker镜像构建

**交付物**：
- 完整的项目文档
- 发布包和安装指南
- Docker部署方案

### 开发里程碑

| 里程碑 | 时间点 | 主要功能 |
|--------|--------|----------|
| M1 | 第2周末 | 基础架构完成，可解析meta文件 |
| M2 | 第4周末 | 核心扫描功能完成，支持基本查询 |
| M3 | 第5.5周末 | 增量扫描和性能优化完成 |
| M4 | 第6.5周末 | CLI界面完善，用户体验优化 |
| M5 | 第7.5周末 | 高级功能完成，支持导出 |
| M6 | 第8.5周末 | 测试完成，性能达标 |
| M7 | 第9周末 | 文档完善，发布就绪 |

## 技术风险分析

### 高风险项

#### 1. Unity版本兼容性风险
**风险描述**：不同Unity版本的文件格式可能存在差异，导致解析失败。

**影响评估**：
- 可能导致部分项目无法扫描
- 解析结果不准确
- 用户体验下降

**缓解策略**：
- 支持多个Unity版本的测试项目
- 实现版本检测和适配机制
- 提供版本特定的解析器
- 建立版本兼容性测试矩阵

**应急预案**：
- 提供手动配置选项
- 实现降级解析模式
- 社区反馈收集机制

#### 2. 大项目性能风险
**风险描述**：超大型Unity项目可能导致内存溢出或扫描时间过长。

**影响评估**：
- 工具无法处理大型项目
- 用户体验差，扫描时间过长
- 系统资源消耗过大

**缓解策略**：
- 实现流式处理和分批处理
- 内存使用监控和限制
- 可配置的资源使用参数
- 增量扫描减少工作量

**应急预案**：
- 提供分块扫描选项
- 临时文件存储中间结果
- 暂停/恢复扫描功能

### 中风险项

#### 3. 复杂依赖关系解析风险
**风险描述**：Unity资源的复杂引用关系可能导致解析错误或遗漏。

**影响评估**：
- 依赖关系不完整
- 误报或漏报问题
- 分析结果不可靠

**缓解策略**：
- 深入研究Unity序列化格式
- 实现多种解析策略
- 提供验证和校对机制
- 建立测试用例库

#### 4. 跨平台兼容性风险
**风险描述**：不同操作系统的文件系统差异可能影响工具运行。

**影响评估**：
- 部分平台无法正常运行
- 路径处理错误
- 编码问题

**缓解策略**：
- 使用标准化的路径处理库
- 统一文件编码处理
- 多平台测试验证
- 条件编译和平台适配

### 低风险项

#### 5. 第三方依赖风险
**风险描述**：依赖的第三方库可能存在安全漏洞或兼容性问题。

**缓解策略**：
- 定期更新依赖库
- 安全漏洞扫描
- 依赖项最小化原则
- 版本锁定和测试

#### 6. 数据库性能风险
**风险描述**：大量数据可能导致数据库查询性能下降。

**缓解策略**：
- 优化数据库索引
- 实现查询缓存
- 分页查询机制
- 数据库维护工具

### 风险监控指标

| 风险类别 | 监控指标 | 阈值 | 处理措施 |
|----------|----------|------|----------|
| 性能风险 | 扫描时间 | >30分钟/万文件 | 优化算法，增加缓存 |
| 内存风险 | 内存使用 | >1GB | 实现流式处理 |
| 准确性风险 | 解析错误率 | >5% | 改进解析器，增加测试 |
| 兼容性风险 | 支持版本覆盖率 | <80% | 扩展版本支持 |

## 质量保证计划

### 测试策略

#### 单元测试
- 每个解析器模块的独立测试
- 配置管理功能测试
- 数据库操作测试
- 工具函数测试
- 目标覆盖率：>90%

#### 集成测试
- 完整扫描流程测试
- 数据库集成测试
- 配置文件加载测试
- 错误处理测试

#### 性能测试
- 大型项目扫描性能测试
- 内存使用测试
- 并发处理测试
- 长时间运行稳定性测试

#### 兼容性测试
- 多Unity版本测试
- 跨平台测试(Windows/macOS/Linux)
- Python版本兼容性测试

### 代码质量标准

```python
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11
  
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.280
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.4.1
    hooks:
      - id: mypy
        additional_dependencies: [types-PyYAML, types-requests]
```

### 持续集成配置

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macOS-latest]
        python-version: [3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install uv
      run: pip install uv
    
    - name: Install dependencies
      run: uv pip install -e .[dev]
    
    - name: Run tests
      run: pytest --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## 总结

本技术设计文档详细描述了Unity资源引用扫描工具的完整技术方案，包括：

1. **深入的需求分析**：基于对Unity资源管理机制的深入研究
2. **完整的技术架构**：模块化设计，支持扩展和维护
3. **性能优化策略**：针对大型项目的特殊优化
4. **用户体验设计**：友好的命令行界面和丰富的功能
5. **详细的实施计划**：分阶段开发，风险可控
6. **全面的质量保证**：测试策略和代码质量标准

该方案充分考虑了Unity项目的复杂性和大型项目的性能需求，提供了一个完整、可执行的技术路线图。通过模块化设计和增量开发，可以确保项目的成功交付和长期维护。

---

**文档状态**: 初版完成  
**下次更新**: 根据开发进展和用户反馈进行更新  
**联系方式**: 通过项目Issue或PR进行反馈
