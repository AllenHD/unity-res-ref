# Unity Resource Reference Scanner - 用户使用指南

## 📋 目录

1. [快速开始](#快速开始)
2. [安装配置](#安装配置)
3. [基础使用](#基础使用)
4. [高级功能](#高级功能)
5. [配置详解](#配置详解)
6. [最佳实践](#最佳实践)
7. [故障排除](#故障排除)
8. [性能优化](#性能优化)

---

## 🚀 快速开始

### 5分钟快速体验

```bash
# 1. 克隆并安装
git clone https://github.com/your-username/unity-res-ref.git
cd unity-res-ref
uv sync

# 2. 初始化Unity项目配置
uv run python -m src.cli.commands init /path/to/your/unity/project

# 3. 执行首次扫描
uv run python -m src.cli.commands scan

# 4. 查看扫描结果
uv run python -m src.cli.commands stats
```

### 预期输出示例

```
🔍 Unity Resource Reference Scanner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 项目配置初始化完成
📁 Unity项目路径: /Users/example/MyUnityProject
⚙️ 配置文件: config/default.yaml

🔄 开始扫描资源文件...
📊 扫描进度: ████████████████████ 100% (1,234 文件)

📈 扫描完成统计:
   • 总文件数: 1,234
   • 资源文件: 856
   • 依赖关系: 2,341
   • 扫描时间: 23.5s
```

---

## 💻 安装配置

### 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| **操作系统** | Windows 10, macOS 10.15, Ubuntu 18.04 | 最新版本 |
| **Python** | 3.11.0 | 3.12+ |
| **内存** | 4GB RAM | 8GB+ RAM |
| **磁盘空间** | 500MB | 2GB+ |
| **Unity版本** | 2019.4 LTS | 2022.3 LTS+ |

### 详细安装步骤

#### Step 1: 安装uv包管理工具

```bash
# macOS/Linux (推荐)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 验证安装
uv --version
```

#### Step 2: 获取项目源码

```bash
# 方式1: Git克隆 (推荐)
git clone https://github.com/your-username/unity-res-ref.git
cd unity-res-ref

# 方式2: 下载ZIP包
wget https://github.com/your-username/unity-res-ref/archive/main.zip
unzip main.zip && cd unity-res-ref-main
```

#### Step 3: 安装项目依赖

```bash
# 安装运行时依赖
uv sync

# 安装开发依赖 (可选)
uv sync --extra dev

# 验证安装
uv run python -m src.cli.commands --version
```

### 环境变量配置

```bash
# ~/.bashrc 或 ~/.zshrc
export UNITY_SCANNER_PROJECT_PATH="/path/to/unity/project"
export UNITY_SCANNER_SCAN_THREADS=8
export UNITY_SCANNER_LOG_LEVEL="INFO"
```

---

## 🎯 基础使用

### 命令行接口概览

```bash
uv run python -m src.cli.commands [COMMAND] [OPTIONS]
```

### 核心命令详解

#### 1. `init` - 项目初始化

**用途**: 为Unity项目创建配置文件和数据库

```bash
# 基础用法
uv run python -m src.cli.commands init /path/to/unity/project

# 指定配置文件路径
uv run python -m src.cli.commands init /path/to/unity/project --config custom.yaml

# 强制覆盖现有配置
uv run python -m src.cli.commands init /path/to/unity/project --force
```

**配置文件示例** (`config/default.yaml`):
```yaml
project:
  name: "MyUnityProject"
  unity_project_path: "/path/to/unity/project"
  unity_version: "2022.3.12f1"

scan:
  paths:
    - "Assets/"
    - "Packages/"
  exclude_paths:
    - "Library/"
    - "Temp/"
    - "StreamingAssets/"
  file_extensions:
    - ".prefab"
    - ".scene"
    - ".asset"
    - ".mat"
    - ".shader"
```

#### 2. `scan` - 资源扫描

**用途**: 扫描Unity项目资源文件，构建依赖关系图

```bash
# 完整扫描
uv run python -m src.cli.commands scan

# 增量扫描 (仅扫描修改的文件)
uv run python -m src.cli.commands scan --incremental

# 指定扫描路径
uv run python -m src.cli.commands scan --path Assets/Scripts/

# 并发扫描 (指定线程数)
uv run python -m src.cli.commands scan --threads 8

# 详细输出
uv run python -m src.cli.commands scan --verbose
```

**扫描过程示例**:
```
🔍 开始扫描 Unity 项目资源...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 扫描路径: Assets/, Packages/
🚫 排除路径: Library/, Temp/
🔧 并发线程: 8

📊 扫描进度:
   Meta文件    ████████████████████ 100% (856/856)
   Prefab文件  ████████████████████ 100% (234/234)  
   Scene文件   ████████████████████ 100% (12/12)
   其他资源    ████████████████████ 100% (132/132)

✅ 扫描完成! 用时: 45.2秒
📈 发现依赖关系: 2,341 个
```

#### 3. `find-deps` - 依赖查询

**用途**: 查询指定资源的依赖关系

```bash
# 查询资源的直接依赖
uv run python -m src.cli.commands find-deps Assets/Player.prefab

# 查询资源的所有依赖 (包括间接依赖)
uv run python -m src.cli.commands find-deps Assets/Player.prefab --recursive

# 查询哪些资源引用了指定资源
uv run python -m src.cli.commands find-deps Assets/Player.prefab --reverse

# 输出到文件
uv run python -m src.cli.commands find-deps Assets/Player.prefab --output deps.json
```

**查询结果示例**:
```json
{
  "asset": "Assets/Player.prefab",
  "guid": "a1b2c3d4e5f6789012345678901234567890abcd",
  "dependencies": [
    {
      "path": "Assets/Materials/PlayerMaterial.mat",
      "guid": "b2c3d4e5f6789012345678901234567890abcdef1",
      "type": "Material"
    },
    {
      "path": "Assets/Scripts/PlayerController.cs",
      "guid": "c3d4e5f6789012345678901234567890abcdef12",
      "type": "MonoScript"
    }
  ],
  "dependency_count": 15,
  "scan_time": "2025-01-15T10:30:45Z"
}
```

#### 4. `detect-circular` - 循环依赖检测

**用途**: 检测项目中的循环依赖问题

```bash
# 检测所有循环依赖
uv run python -m src.cli.commands detect-circular

# 只显示强连通组件
uv run python -m src.cli.commands detect-circular --scc-only

# 生成详细报告
uv run python -m src.cli.commands detect-circular --report circular_deps.md

# 尝试修复建议
uv run python -m src.cli.commands detect-circular --suggest-fixes
```

**循环依赖报告示例**:
```markdown
# 循环依赖检测报告

## 检测摘要
- 总资源数: 1,234
- 循环依赖组数: 3
- 涉及资源数: 8
- 严重程度: ⚠️ 中等

## 循环依赖详情

### 循环组 #1 (长度: 3)
```
Assets/UI/MainMenu.prefab 
  → Assets/UI/SubMenu.prefab 
  → Assets/UI/Components/Button.prefab 
  → Assets/UI/MainMenu.prefab
```

**修复建议**: 
- 将共同依赖提取到独立的ScriptableObject中
- 使用Unity的Addressable资源管理系统
```

#### 5. `export` - 数据导出

**用途**: 将分析结果导出为不同格式

```bash
# 导出为JSON格式
uv run python -m src.cli.commands export --format json --output results.json

# 导出为CSV格式
uv run python -m src.cli.commands export --format csv --output results.csv

# 导出为DOT格式 (可用于Graphviz可视化)
uv run python -m src.cli.commands export --format dot --output graph.dot

# 生成HTML报告
uv run python -m src.cli.commands export --format html --output report.html

# 导出统计信息
uv run python -m src.cli.commands export --stats-only --output stats.json
```

#### 6. `stats` - 统计信息

**用途**: 显示项目资源统计信息

```bash
# 基础统计
uv run python -m src.cli.commands stats

# 详细统计
uv run python -m src.cli.commands stats --detailed

# 按文件类型分组统计
uv run python -m src.cli.commands stats --by-type

# 历史统计对比
uv run python -m src.cli.commands stats --history
```

**统计输出示例**:
```
📊 Unity项目资源统计报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 项目概览:
   项目名称: MyUnityProject
   Unity版本: 2022.3.12f1
   扫描时间: 2025-01-15 10:30:45
   扫描耗时: 45.2秒

📁 文件统计:
   ├── 总文件数: 1,234
   ├── 资源文件: 856 (69.4%)
   ├── 脚本文件: 245 (19.9%)
   └── 其他文件: 133 (10.8%)

🔗 依赖关系:
   ├── 总依赖数: 2,341
   ├── 平均每资源: 2.7个依赖
   ├── 最大依赖数: 23 (Assets/MainScene.unity)
   └── 循环依赖组: 3个

📊 文件类型分布:
   Prefab   ████████████████ 234 (27.3%)
   Material ███████████████ 198 (23.1%) 
   Texture  ██████████████ 156 (18.2%)
   Scene    ████████ 12 (1.4%)
   Other    ██████████████████████ 256 (29.9%)
```

---

## 🔧 高级功能

### 增量扫描优化

增量扫描功能可以显著减少大型项目的扫描时间：

```bash
# 首次完整扫描
uv run python -m src.cli.commands scan

# 后续增量扫描 (仅处理修改的文件)
uv run python -m src.cli.commands scan --incremental

# 强制重新扫描特定路径
uv run python -m src.cli.commands scan --path Assets/NewFeature/ --force
```

**增量扫描原理**:
- 基于文件修改时间(`mtime`)检测变化
- 数据库存储上次扫描时间戳
- 智能识别新增、修改、删除的文件
- 只重新解析变化的文件及其依赖

### 性能监控和调优

```bash
# 启用性能监控
uv run python -m src.cli.commands scan --profile

# 内存使用优化
uv run python -m src.cli.commands scan --memory-limit 2GB

# 磁盘I/O优化
uv run python -m src.cli.commands scan --batch-size 1000

# 网络存储优化
uv run python -m src.cli.commands scan --network-timeout 30
```

### 并发和多线程

```bash
# 自动检测CPU核心数
uv run python -m src.cli.commands scan --auto-threads

# 手动指定线程数
uv run python -m src.cli.commands scan --threads 16

# I/O密集型优化
uv run python -m src.cli.commands scan --io-intensive

# CPU密集型优化  
uv run python -m src.cli.commands scan --cpu-intensive
```

### 高级查询功能

#### 复杂依赖查询

```bash
# 查询深度依赖 (最多N层)
uv run python -m src.cli.commands find-deps Assets/Player.prefab --max-depth 5

# 查询特定类型的依赖
uv run python -m src.cli.commands find-deps Assets/Player.prefab --type Material,Texture

# 排除特定路径的依赖
uv run python -m src.cli.commands find-deps Assets/Player.prefab --exclude "Packages/*"

# 查询共同依赖
uv run python -m src.cli.commands find-common-deps Assets/A.prefab Assets/B.prefab
```

#### 未使用资源检测

```bash
# 检测所有未使用资源
uv run python -m src.cli.commands find-unused

# 按文件类型检测
uv run python -m src.cli.commands find-unused --type Texture,Audio

# 排除特定路径
uv run python -m src.cli.commands find-unused --exclude "Assets/Archive/*"

# 生成清理脚本
uv run python -m src.cli.commands find-unused --generate-cleanup-script
```

### 数据库管理

```bash
# 数据库状态检查
uv run python -m src.cli.commands db-status

# 数据库备份
uv run python -m src.cli.commands db-backup --output backup_20250115.db

# 数据库恢复
uv run python -m src.cli.commands db-restore backup_20250115.db

# 数据库清理 (删除过期数据)
uv run python -m src.cli.commands db-cleanup --days 30

# 数据库重建
uv run python -m src.cli.commands db-rebuild
```

---

## ⚙️ 配置详解

### 配置文件结构

完整的配置文件示例 (`config/default.yaml`):

```yaml
# 项目基础配置
project:
  name: "MyUnityProject"
  unity_project_path: "/path/to/unity/project"
  unity_version: "2022.3.12f1"
  description: "项目描述信息"

# 扫描配置
scan:
  # 扫描路径 (相对于Unity项目根目录)
  paths:
    - "Assets/"
    - "Packages/"
    - "ProjectSettings/"
  
  # 排除路径
  exclude_paths:
    - "Library/"
    - "Temp/"
    - "Logs/"
    - "StreamingAssets/"
    - "*.tmp"
  
  # 支持的文件扩展名
  file_extensions:
    - ".prefab"
    - ".scene" 
    - ".asset"
    - ".mat"
    - ".shader"
    - ".cs"
    - ".js"
    - ".png"
    - ".jpg"
    - ".wav"
    - ".mp3"
  
  # 扫描选项
  follow_symlinks: false
  max_file_size_mb: 100
  enable_checksum: true

# 数据库配置
database:
  type: "sqlite"
  path: "unity_deps.db"
  backup_enabled: true
  backup_interval_hours: 24
  cleanup_days: 30
  
  # 连接池配置
  pool_size: 10
  max_overflow: 20
  pool_timeout: 30

# 性能配置
performance:
  # 并发设置
  max_workers: 0  # 0表示自动检测CPU核心数
  thread_pool_size: 10
  process_pool_size: 4
  
  # 内存管理
  memory_limit_mb: 2048
  batch_size: 1000
  cache_size_mb: 256
  
  # I/O优化
  disk_buffer_size: 8192
  network_timeout: 30
  retry_attempts: 3

# 输出配置
output:
  verbosity: "info"  # debug, info, warning, error
  progress_bar: true
  color_output: true
  log_file: "logs/scanner.log"
  log_rotation: true
  max_log_size_mb: 50
  
  # 导出格式
  export_formats:
    - "json"
    - "csv" 
    - "dot"
    - "html"

# 功能特性开关
features:
  detect_unused_assets: true
  detect_circular_deps: true
  generate_reports: true
  enable_incremental_scan: true
  auto_backup: true
  
  # 实验性功能
  experimental:
    deep_analysis: false
    ai_suggestions: false
    web_interface: false

# 报告配置
reports:
  # HTML报告设置
  html:
    template: "default"
    include_thumbnails: true
    interactive_graphs: true
    
  # 统计报告设置
  statistics:
    include_history: true
    chart_types: ["bar", "pie", "line"]
    
  # 导出设置
  export:
    compress_output: true
    include_metadata: true
    timestamp_files: true
```

### 环境变量配置

支持通过环境变量覆盖配置文件设置：

```bash
# 项目路径
export UNITY_SCANNER_PROJECT_UNITY_PROJECT_PATH="/path/to/project"

# 扫描配置
export UNITY_SCANNER_SCAN_MAX_WORKERS=16
export UNITY_SCANNER_SCAN_BATCH_SIZE=2000

# 数据库配置
export UNITY_SCANNER_DATABASE_PATH="custom_db.sqlite"

# 性能配置
export UNITY_SCANNER_PERFORMANCE_MEMORY_LIMIT_MB=4096

# 输出配置
export UNITY_SCANNER_OUTPUT_VERBOSITY="debug"
export UNITY_SCANNER_OUTPUT_LOG_FILE="custom.log"
```

### 配置验证

```bash
# 验证配置文件语法
uv run python -m src.cli.commands config validate

# 显示当前配置
uv run python -m src.cli.commands config show

# 生成默认配置
uv run python -m src.cli.commands config generate-default

# 配置文件迁移
uv run python -m src.cli.commands config migrate --from v1.0 --to v2.0
```

---

## 💡 最佳实践

### 项目组织建议

#### 1. 目录结构最佳实践

```
MyUnityProject/
├── Assets/
│   ├── _Project/           # 项目特定资源
│   │   ├── Scripts/
│   │   ├── Prefabs/
│   │   ├── Materials/
│   │   └── Scenes/
│   ├── Art/                # 美术资源
│   │   ├── Textures/
│   │   ├── Models/
│   │   └── Animations/
│   ├── Audio/              # 音频资源
│   ├── Plugins/            # 第三方插件
│   └── StreamingAssets/    # 流式资源
├── Packages/               # 包管理器资源
├── ProjectSettings/        # 项目设置
└── unity-res-ref/          # 扫描工具目录
    ├── config/
    ├── logs/
    └── reports/
```

#### 2. 配置文件管理

```bash
# 为不同环境创建配置文件
config/
├── default.yaml           # 默认配置
├── development.yaml       # 开发环境
├── staging.yaml          # 测试环境
└── production.yaml       # 生产环境

# 使用环境特定配置
export UNITY_SCANNER_CONFIG=config/development.yaml
uv run python -m src.cli.commands scan
```

#### 3. 扫描策略

```bash
# 首次完整扫描
uv run python -m src.cli.commands scan --full

# 日常增量扫描
uv run python -m src.cli.commands scan --incremental

# 特定功能开发时
uv run python -m src.cli.commands scan --path Assets/NewFeature/

# 发布前完整检查
uv run python -m src.cli.commands scan --full --detect-unused --detect-circular
```

### 性能优化建议

#### 1. 大型项目优化

对于超过10万文件的大型Unity项目：

```yaml
# config/large_project.yaml
performance:
  max_workers: 16
  batch_size: 2000
  memory_limit_mb: 8192
  
scan:
  exclude_paths:
    - "Assets/StreamingAssets/*"
    - "Assets/Archive/*"
    - "*.fbx.meta"  # 排除大型模型的meta文件
    
database:
  pool_size: 20
  cleanup_days: 7  # 更频繁的清理
```

#### 2. 网络存储优化

对于存储在网络驱动器上的项目：

```yaml
performance:
  network_timeout: 60
  retry_attempts: 5
  disk_buffer_size: 16384
  
scan:
  enable_checksum: false  # 禁用校验和以提升速度
  max_file_size_mb: 50   # 限制文件大小
```

#### 3. 内存优化

对于内存受限的环境：

```yaml
performance:
  memory_limit_mb: 1024
  batch_size: 500
  cache_size_mb: 64
  
features:
  experimental:
    deep_analysis: false  # 禁用深度分析
```

### 团队协作建议

#### 1. 集成到CI/CD流程

```yaml
# .github/workflows/unity-scan.yml
name: Unity Resource Scan
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install uv
        run: pip install uv
      - name: Install dependencies
        run: uv sync
      - name: Run Unity scan
        run: |
          uv run python -m src.cli.commands scan --incremental
          uv run python -m src.cli.commands detect-circular --report circular.md
      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: scan-reports
          path: reports/
```

#### 2. 代码审查集成

```bash
# pre-commit 钩子
#!/bin/bash
# .git/hooks/pre-commit

# 检查是否有Unity资源变更
git diff --cached --name-only | grep -E '\.(prefab|scene|asset)$' > /dev/null

if [ $? -eq 0 ]; then
    echo "检测到Unity资源变更，执行增量扫描..."
    uv run python -m src.cli.commands scan --incremental --quiet
    
    # 检查循环依赖
    uv run python -m src.cli.commands detect-circular --quiet
    if [ $? -ne 0 ]; then
        echo "❌ 发现循环依赖，请修复后再提交"
        exit 1
    fi
    
    echo "✅ 资源扫描通过"
fi
```

#### 3. 团队配置共享

```bash
# 团队配置模板
config/
├── team.yaml              # 团队通用配置
├── .env.template          # 环境变量模板
└── README.md             # 配置说明

# .env.template
UNITY_SCANNER_PROJECT_UNITY_PROJECT_PATH=/path/to/project
UNITY_SCANNER_PERFORMANCE_MAX_WORKERS=8
UNITY_SCANNER_OUTPUT_VERBOSITY=info
```

---

## 🚨 故障排除

### 常见问题和解决方案

#### 1. 安装和配置问题

**Q: `uv: command not found`**
```bash
# 解决方案：重新安装uv并添加到PATH
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # 或 ~/.zshrc
```

**Q: Python版本不兼容**
```bash
# 检查Python版本
python --version

# 使用uv管理Python版本
uv python install 3.11
uv python pin 3.11
```

**Q: 依赖安装失败**
```bash
# 清理缓存重新安装
uv cache clean
rm -rf .venv
uv sync --reinstall
```

#### 2. 扫描过程问题

**Q: 扫描速度过慢**
```bash
# 检查系统资源使用
uv run python -m src.cli.commands scan --profile

# 优化配置
export UNITY_SCANNER_PERFORMANCE_MAX_WORKERS=16
export UNITY_SCANNER_SCAN_BATCH_SIZE=2000
```

**Q: 内存不足错误**
```bash
# 限制内存使用
uv run python -m src.cli.commands scan --memory-limit 1GB

# 使用流式处理
uv run python -m src.cli.commands scan --streaming
```

**Q: 文件权限错误**
```bash
# 检查文件权限
ls -la /path/to/unity/project

# 修复权限问题
chmod -R 755 /path/to/unity/project
```

#### 3. 数据库问题

**Q: 数据库锁定错误**
```bash
# 检查数据库状态
uv run python -m src.cli.commands db-status

# 强制解锁
uv run python -m src.cli.commands db-unlock

# 重建数据库
uv run python -m src.cli.commands db-rebuild
```

**Q: 数据库损坏**
```bash
# 从备份恢复
uv run python -m src.cli.commands db-restore backup.db

# 重新扫描重建
rm unity_deps.db*
uv run python -m src.cli.commands scan --full
```

#### 4. 解析错误

**Q: Meta文件解析失败**
```bash
# 检查具体错误
uv run python -m src.cli.commands scan --verbose --debug

# 跳过错误文件继续扫描
uv run python -m src.cli.commands scan --ignore-errors
```

**Q: Unity版本不兼容**
```bash
# 检查支持的Unity版本
uv run python -m src.cli.commands --supported-unity-versions

# 强制兼容模式
uv run python -m src.cli.commands scan --force-compatibility
```

### 调试和日志

#### 启用详细日志

```bash
# 设置日志级别
export UNITY_SCANNER_OUTPUT_VERBOSITY=debug

# 启用文件日志
export UNITY_SCANNER_OUTPUT_LOG_FILE=debug.log

# 运行扫描
uv run python -m src.cli.commands scan --verbose
```

#### 性能分析

```bash
# 启用性能分析
uv run python -m src.cli.commands scan --profile --profile-output profile.json

# 分析性能报告
uv run python -c "
import json
with open('profile.json') as f:
    data = json.load(f)
    print(f'Total time: {data[\"total_time\"]:.2f}s')
    print(f'File parsing: {data[\"parsing_time\"]:.2f}s')
    print(f'Database ops: {data[\"db_time\"]:.2f}s')
"
```

#### 内存使用监控

```bash
# 启用内存监控
uv run python -m src.cli.commands scan --memory-monitor

# 生成内存使用报告
uv run python -m src.cli.commands scan --memory-report memory.json
```

---

## ⚡ 性能优化

### 系统级优化

#### 1. 硬件配置建议

| 项目规模 | CPU | 内存 | 存储 | 网络 |
|----------|-----|------|------|------|
| **小型** (<1万文件) | 4核 | 4GB | SSD | 本地 |
| **中型** (1-5万文件) | 8核 | 8GB | NVMe SSD | 千兆 |
| **大型** (5-20万文件) | 16核 | 16GB | 高速NVMe | 万兆 |
| **超大型** (>20万文件) | 32核 | 32GB | RAID NVMe | 专线 |

#### 2. 操作系统优化

**Linux/macOS**:
```bash
# 增加文件描述符限制
ulimit -n 65536
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 优化磁盘I/O调度
echo mq-deadline > /sys/block/sda/queue/scheduler

# 增加虚拟内存
sysctl vm.max_map_count=262144
```

**Windows**:
```powershell
# 增加虚拟内存
# 控制面板 → 系统 → 高级系统设置 → 性能设置 → 高级 → 虚拟内存

# 禁用Windows Defender实时监控 (针对项目目录)
Add-MpPreference -ExclusionPath "C:\Unity\Projects"
```

### 应用级优化

#### 1. 配置优化

```yaml
# config/performance.yaml
performance:
  # CPU密集型任务优化
  max_workers: 0  # 自动检测CPU核心数
  thread_pool_size: 32
  
  # 内存优化
  memory_limit_mb: 0  # 不限制内存
  batch_size: 5000
  cache_size_mb: 1024
  
  # I/O优化
  disk_buffer_size: 32768
  prefetch_size: 1000
  
  # 网络优化 (适用于网络存储)
  network_timeout: 120
  connection_pool_size: 20
  retry_backoff: 2.0

scan:
  # 并行扫描优化
  parallel_meta_parsing: true
  parallel_dependency_analysis: true
  
  # 缓存优化
  enable_file_cache: true
  cache_meta_content: true
  cache_guid_mappings: true
  
  # 跳过不必要的处理
  skip_unchanged_files: true
  skip_large_files_threshold_mb: 500
  
database:
  # 数据库性能优化
  journal_mode: "WAL"  # Write-Ahead Logging
  synchronous: "NORMAL"
  cache_size: -64000  # 64MB缓存
  temp_store: "MEMORY"
  
  # 批量操作优化
  batch_insert_size: 10000
  transaction_size: 50000
```

#### 2. 运行时优化

```bash
# 使用性能配置文件
export UNITY_SCANNER_CONFIG=config/performance.yaml

# 预分配系统资源
export MALLOC_ARENA_MAX=4
export OMP_NUM_THREADS=16

# 优化Python垃圾回收
export PYTHONHASHSEED=0
export PYTHONUNBUFFERED=1

# 运行扫描
uv run python -O -m src.cli.commands scan --performance-mode
```

### 特定场景优化

#### 1. 网络存储项目

```yaml
# config/network_storage.yaml
performance:
  network_timeout: 300
  retry_attempts: 10
  connection_pool_size: 50
  
scan:
  # 减少网络I/O
  enable_checksum: false
  cache_file_stats: true
  prefetch_meta_files: true
  
  # 批量处理
  batch_size: 1000
  meta_batch_size: 500
```

#### 2. 大型Prefab项目

```yaml
# config/large_prefabs.yaml
scan:
  # Prefab特殊处理
  prefab_deep_parse: false
  skip_nested_prefabs: true
  max_prefab_depth: 5
  
performance:
  # 针对大型YAML文件优化
  yaml_buffer_size: 65536
  streaming_yaml_parser: true
```

#### 3. 多版本Unity项目

```yaml
# config/multi_version.yaml
scan:
  # 版本兼容处理
  unity_version_detection: true
  backward_compatibility: true
  skip_version_conflicts: true
  
  # 路径优化
  version_specific_exclusions:
    "2019.4": ["Assets/2022Features/"]
    "2022.3": ["Assets/LegacyAssets/"]
```

### 监控和基准测试

#### 1. 性能基准测试

```bash
# 创建基准测试
uv run python -m src.cli.commands benchmark --create baseline

# 运行性能测试
uv run python -m src.cli.commands benchmark --run --compare baseline

# 生成性能报告
uv run python -m src.cli.commands benchmark --report performance.html
```

#### 2. 实时监控

```bash
# 启用实时监控
uv run python -m src.cli.commands scan --monitor --monitor-interval 5

# 监控输出示例
Monitor Report (Every 5s):
  CPU Usage: 85.3%
  Memory: 2.1GB / 16GB (13.1%)
  Disk I/O: Read 45MB/s, Write 12MB/s
  Files Processed: 12,345 / 50,000 (24.7%)
  Current Rate: 245 files/s
  ETA: 2min 35s
```

#### 3. 性能分析工具

```bash
# Python性能分析
uv run python -m cProfile -o profile.stats -m src.cli.commands scan
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"

# 内存分析
uv run python -m memory_profiler -m src.cli.commands scan --memory-profile

# 并发分析
uv run python -m src.cli.commands scan --concurrency-profile threads.json
```

---

这个详细的使用指南涵盖了Unity Resource Reference Scanner的所有核心功能和高级特性。用户可以根据自己的项目需求和技术水平，选择合适的使用方式。文档结构清晰，包含大量实用的代码示例和配置模板，能够帮助用户快速上手并充分利用工具的各种功能。// filepath: docs/USER_GUIDE.md
# Unity Resource Reference Scanner - 用户使用指南

## 📋 目录

1. [快速开始](#快速开始)
2. [安装配置](#安装配置)
3. [基础使用](#基础使用)
4. [高级功能](#高级功能)
5. [配置详解](#配置详解)
6. [最佳实践](#最佳实践)
7. [故障排除](#故障排除)
8. [性能优化](#性能优化)

---

## 🚀 快速开始

### 5分钟快速体验

```bash
# 1. 克隆并安装
git clone https://github.com/your-username/unity-res-ref.git
cd unity-res-ref
uv sync

# 2. 初始化Unity项目配置
uv run python -m src.cli.commands init /path/to/your/unity/project

# 3. 执行首次扫描
uv run python -m src.cli.commands scan

# 4. 查看扫描结果
uv run python -m src.cli.commands stats
```

### 预期输出示例

```
🔍 Unity Resource Reference Scanner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 项目配置初始化完成
📁 Unity项目路径: /Users/example/MyUnityProject
⚙️ 配置文件: config/default.yaml

🔄 开始扫描资源文件...
📊 扫描进度: ████████████████████ 100% (1,234 文件)

📈 扫描完成统计:
   • 总文件数: 1,234
   • 资源文件: 856
   • 依赖关系: 2,341
   • 扫描时间: 23.5s
```

---

## 💻 安装配置

### 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| **操作系统** | Windows 10, macOS 10.15, Ubuntu 18.04 | 最新版本 |
| **Python** | 3.11.0 | 3.12+ |
| **内存** | 4GB RAM | 8GB+ RAM |
| **磁盘空间** | 500MB | 2GB+ |
| **Unity版本** | 2019.4 LTS | 2022.3 LTS+ |

### 详细安装步骤

#### Step 1: 安装uv包管理工具

```bash
# macOS/Linux (推荐)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 验证安装
uv --version
```

#### Step 2: 获取项目源码

```bash
# 方式1: Git克隆 (推荐)
git clone https://github.com/your-username/unity-res-ref.git
cd unity-res-ref

# 方式2: 下载ZIP包
wget https://github.com/your-username/unity-res-ref/archive/main.zip
unzip main.zip && cd unity-res-ref-main
```

#### Step 3: 安装项目依赖

```bash
# 安装运行时依赖
uv sync

# 安装开发依赖 (可选)
uv sync --extra dev

# 验证安装
uv run python -m src.cli.commands --version
```

### 环境变量配置

```bash
# ~/.bashrc 或 ~/.zshrc
export UNITY_SCANNER_PROJECT_PATH="/path/to/unity/project"
export UNITY_SCANNER_SCAN_THREADS=8
export UNITY_SCANNER_LOG_LEVEL="INFO"
```

---

## 🎯 基础使用

### 命令行接口概览

```bash
uv run python -m src.cli.commands [COMMAND] [OPTIONS]
```

### 核心命令详解

#### 1. `init` - 项目初始化

**用途**: 为Unity项目创建配置文件和数据库

```bash
# 基础用法
uv run python -m src.cli.commands init /path/to/unity/project

# 指定配置文件路径
uv run python -m src.cli.commands init /path/to/unity/project --config custom.yaml

# 强制覆盖现有配置
uv run python -m src.cli.commands init /path/to/unity/project --force
```

**配置文件示例** (`config/default.yaml`):
```yaml
project:
  name: "MyUnityProject"
  unity_project_path: "/path/to/unity/project"
  unity_version: "2022.3.12f1"

scan:
  paths:
    - "Assets/"
    - "Packages/"
  exclude_paths:
    - "Library/"
    - "Temp/"
    - "StreamingAssets/"
  file_extensions:
    - ".prefab"
    - ".scene"
    - ".asset"
    - ".mat"
    - ".shader"
```

#### 2. `scan` - 资源扫描

**用途**: 扫描Unity项目资源文件，构建依赖关系图

```bash
# 完整扫描
uv run python -m src.cli.commands scan

# 增量扫描 (仅扫描修改的文件)
uv run python -m src.cli.commands scan --incremental

# 指定扫描路径
uv run python -m src.cli.commands scan --path Assets/Scripts/

# 并发扫描 (指定线程数)
uv run python -m src.cli.commands scan --threads 8

# 详细输出
uv run python -m src.cli.commands scan --verbose
```

**扫描过程示例**:
```
🔍 开始扫描 Unity 项目资源...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 扫描路径: Assets/, Packages/
🚫 排除路径: Library/, Temp/
🔧 并发线程: 8

📊 扫描进度:
   Meta文件    ████████████████████ 100% (856/856)
   Prefab文件  ████████████████████ 100% (234/234)  
   Scene文件   ████████████████████ 100% (12/12)
   其他资源    ████████████████████ 100% (132/132)

✅ 扫描完成! 用时: 45.2秒
📈 发现依赖关系: 2,341 个
```

#### 3. `find-deps` - 依赖查询

**用途**: 查询指定资源的依赖关系

```bash
# 查询资源的直接依赖
uv run python -m src.cli.commands find-deps Assets/Player.prefab

# 查询资源的所有依赖 (包括间接依赖)
uv run python -m src.cli.commands find-deps Assets/Player.prefab --recursive

# 查询哪些资源引用了指定资源
uv run python -m src.cli.commands find-deps Assets/Player.prefab --reverse

# 输出到文件
uv run python -m src.cli.commands find-deps Assets/Player.prefab --output deps.json
```

**查询结果示例**:
```json
{
  "asset": "Assets/Player.prefab",
  "guid": "a1b2c3d4e5f6789012345678901234567890abcd",
  "dependencies": [
    {
      "path": "Assets/Materials/PlayerMaterial.mat",
      "guid": "b2c3d4e5f6789012345678901234567890abcdef1",
      "type": "Material"
    },
    {
      "path": "Assets/Scripts/PlayerController.cs",
      "guid": "c3d4e5f6789012345678901234567890abcdef12",
      "type": "MonoScript"
    }
  ],
  "dependency_count": 15,
  "scan_time": "2025-01-15T10:30:45Z"
}
```

#### 4. `detect-circular` - 循环依赖检测

**用途**: 检测项目中的循环依赖问题

```bash
# 检测所有循环依赖
uv run python -m src.cli.commands detect-circular

# 只显示强连通组件
uv run python -m src.cli.commands detect-circular --scc-only

# 生成详细报告
uv run python -m src.cli.commands detect-circular --report circular_deps.md

# 尝试修复建议
uv run python -m src.cli.commands detect-circular --suggest-fixes
```

**循环依赖报告示例**:
```markdown
# 循环依赖检测报告

## 检测摘要
- 总资源数: 1,234
- 循环依赖组数: 3
- 涉及资源数: 8
- 严重程度: ⚠️ 中等

## 循环依赖详情

### 循环组 #1 (长度: 3)
```
Assets/UI/MainMenu.prefab 
  → Assets/UI/SubMenu.prefab 
  → Assets/UI/Components/Button.prefab 
  → Assets/UI/MainMenu.prefab
```

**修复建议**: 
- 将共同依赖提取到独立的ScriptableObject中
- 使用Unity的Addressable资源管理系统
```

#### 5. `export` - 数据导出

**用途**: 将分析结果导出为不同格式

```bash
# 导出为JSON格式
uv run python -m src.cli.commands export --format json --output results.json

# 导出为CSV格式
uv run python -m src.cli.commands export --format csv --output results.csv

# 导出为DOT格式 (可用于Graphviz可视化)
uv run python -m src.cli.commands export --format dot --output graph.dot

# 生成HTML报告
uv run python -m src.cli.commands export --format html --output report.html

# 导出统计信息
uv run python -m src.cli.commands export --stats-only --output stats.json
```

#### 6. `stats` - 统计信息

**用途**: 显示项目资源统计信息

```bash
# 基础统计
uv run python -m src.cli.commands stats

# 详细统计
uv run python -m src.cli.commands stats --detailed

# 按文件类型分组统计
uv run python -m src.cli.commands stats --by-type

# 历史统计对比
uv run python -m src.cli.commands stats --history
```

**统计输出示例**:
```
📊 Unity项目资源统计报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 项目概览:
   项目名称: MyUnityProject
   Unity版本: 2022.3.12f1
   扫描时间: 2025-01-15 10:30:45
   扫描耗时: 45.2秒

📁 文件统计:
   ├── 总文件数: 1,234
   ├── 资源文件: 856 (69.4%)
   ├── 脚本文件: 245 (19.9%)
   └── 其他文件: 133 (10.8%)

🔗 依赖关系:
   ├── 总依赖数: 2,341
   ├── 平均每资源: 2.7个依赖
   ├── 最大依赖数: 23 (Assets/MainScene.unity)
   └── 循环依赖组: 3个

📊 文件类型分布:
   Prefab   ████████████████ 234 (27.3%)
   Material ███████████████ 198 (23.1%) 
   Texture  ██████████████ 156 (18.2%)
   Scene    ████████ 12 (1.4%)
   Other    ██████████████████████ 256 (29.9%)
```

---

## 🔧 高级功能

### 增量扫描优化

增量扫描功能可以显著减少大型项目的扫描时间：

```bash
# 首次完整扫描
uv run python -m src.cli.commands scan

# 后续增量扫描 (仅处理修改的文件)
uv run python -m src.cli.commands scan --incremental

# 强制重新扫描特定路径
uv run python -m src.cli.commands scan --path Assets/NewFeature/ --force
```

**增量扫描原理**:
- 基于文件修改时间(`mtime`)检测变化
- 数据库存储上次扫描时间戳
- 智能识别新增、修改、删除的文件
- 只重新解析变化的文件及其依赖

### 性能监控和调优

```bash
# 启用性能监控
uv run python -m src.cli.commands scan --profile

# 内存使用优化
uv run python -m src.cli.commands scan --memory-limit 2GB

# 磁盘I/O优化
uv run python -m src.cli.commands scan --batch-size 1000

# 网络存储优化
uv run python -m src.cli.commands scan --network-timeout 30
```

### 并发和多线程

```bash
# 自动检测CPU核心数
uv run python -m src.cli.commands scan --auto-threads

# 手动指定线程数
uv run python -m src.cli.commands scan --threads 16

# I/O密集型优化
uv run python -m src.cli.commands scan --io-intensive

# CPU密集型优化  
uv run python -m src.cli.commands scan --cpu-intensive
```

### 高级查询功能

#### 复杂依赖查询

```bash
# 查询深度依赖 (最多N层)
uv run python -m src.cli.commands find-deps Assets/Player.prefab --max-depth 5

# 查询特定类型的依赖
uv run python -m src.cli.commands find-deps Assets/Player.prefab --type Material,Texture

# 排除特定路径的依赖
uv run python -m src.cli.commands find-deps Assets/Player.prefab --exclude "Packages/*"

# 查询共同依赖
uv run python -m src.cli.commands find-common-deps Assets/A.prefab Assets/B.prefab
```

#### 未使用资源检测

```bash
# 检测所有未使用资源
uv run python -m src.cli.commands find-unused

# 按文件类型检测
uv run python -m src.cli.commands find-unused --type Texture,Audio

# 排除特定路径
uv run python -m src.cli.commands find-unused --exclude "Assets/Archive/*"

# 生成清理脚本
uv run python -m src.cli.commands find-unused --generate-cleanup-script
```

### 数据库管理

```bash
# 数据库状态检查
uv run python -m src.cli.commands db-status

# 数据库备份
uv run python -m src.cli.commands db-backup --output backup_20250115.db

# 数据库恢复
uv run python -m src.cli.commands db-restore backup_20250115.db

# 数据库清理 (删除过期数据)
uv run python -m src.cli.commands db-cleanup --days 30

# 数据库重建
uv run python -m src.cli.commands db-rebuild
```

---

## ⚙️ 配置详解

### 配置文件结构

完整的配置文件示例 (`config/default.yaml`):

```yaml
# 项目基础配置
project:
  name: "MyUnityProject"
  unity_project_path: "/path/to/unity/project"
  unity_version: "2022.3.12f1"
  description: "项目描述信息"

# 扫描配置
scan:
  # 扫描路径 (相对于Unity项目根目录)
  paths:
    - "Assets/"
    - "Packages/"
    - "ProjectSettings/"
  
  # 排除路径
  exclude_paths:
    - "Library/"
    - "Temp/"
    - "Logs/"
    - "StreamingAssets/"
    - "*.tmp"
  
  # 支持的文件扩展名
  file_extensions:
    - ".prefab"
    - ".scene" 
    - ".asset"
    - ".mat"
    - ".shader"
    - ".cs"
    - ".js"
    - ".png"
    - ".jpg"
    - ".wav"
    - ".mp3"
  
  # 扫描选项
  follow_symlinks: false
  max_file_size_mb: 100
  enable_checksum: true

# 数据库配置
database:
  type: "sqlite"
  path: "unity_deps.db"
  backup_enabled: true
  backup_interval_hours: 24
  cleanup_days: 30
  
  # 连接池配置
  pool_size: 10
  max_overflow: 20
  pool_timeout: 30

# 性能配置
performance:
  # 并发设置
  max_workers: 0  # 0表示自动检测CPU核心数
  thread_pool_size: 10
  process_pool_size: 4
  
  # 内存管理
  memory_limit_mb: 2048
  batch_size: 1000
  cache_size_mb: 256
  
  # I/O优化
  disk_buffer_size: 8192
  network_timeout: 30
  retry_attempts: 3

# 输出配置
output:
  verbosity: "info"  # debug, info, warning, error
  progress_bar: true
  color_output: true
  log_file: "logs/scanner.log"
  log_rotation: true
  max_log_size_mb: 50
  
  # 导出格式
  export_formats:
    - "json"
    - "csv" 
    - "dot"
    - "html"

# 功能特性开关
features:
  detect_unused_assets: true
  detect_circular_deps: true
  generate_reports: true
  enable_incremental_scan: true
  auto_backup: true
  
  # 实验性功能
  experimental:
    deep_analysis: false
    ai_suggestions: false
    web_interface: false

# 报告配置
reports:
  # HTML报告设置
  html:
    template: "default"
    include_thumbnails: true
    interactive_graphs: true
    
  # 统计报告设置
  statistics:
    include_history: true
    chart_types: ["bar", "pie", "line"]
    
  # 导出设置
  export:
    compress_output: true
    include_metadata: true
    timestamp_files: true
```

### 环境变量配置

支持通过环境变量覆盖配置文件设置：

```bash
# 项目路径
export UNITY_SCANNER_PROJECT_UNITY_PROJECT_PATH="/path/to/project"

# 扫描配置
export UNITY_SCANNER_SCAN_MAX_WORKERS=16
export UNITY_SCANNER_SCAN_BATCH_SIZE=2000

# 数据库配置
export UNITY_SCANNER_DATABASE_PATH="custom_db.sqlite"

# 性能配置
export UNITY_SCANNER_PERFORMANCE_MEMORY_LIMIT_MB=4096

# 输出配置
export UNITY_SCANNER_OUTPUT_VERBOSITY="debug"
export UNITY_SCANNER_OUTPUT_LOG_FILE="custom.log"
```

### 配置验证

```bash
# 验证配置文件语法
uv run python -m src.cli.commands config validate

# 显示当前配置
uv run python -m src.cli.commands config show

# 生成默认配置
uv run python -m src.cli.commands config generate-default

# 配置文件迁移
uv run python -m src.cli.commands config migrate --from v1.0 --to v2.0
```

---

## 💡 最佳实践

### 项目组织建议

#### 1. 目录结构最佳实践

```
MyUnityProject/
├── Assets/
│   ├── _Project/           # 项目特定资源
│   │   ├── Scripts/
│   │   ├── Prefabs/
│   │   ├── Materials/
│   │   └── Scenes/
│   ├── Art/                # 美术资源
│   │   ├── Textures/
│   │   ├── Models/
│   │   └── Animations/
│   ├── Audio/              # 音频资源
│   ├── Plugins/            # 第三方插件
│   └── StreamingAssets/    # 流式资源
├── Packages/               # 包管理器资源
├── ProjectSettings/        # 项目设置
└── unity-res-ref/          # 扫描工具目录
    ├── config/
    ├── logs/
    └── reports/
```

#### 2. 配置文件管理

```bash
# 为不同环境创建配置文件
config/
├── default.yaml           # 默认配置
├── development.yaml       # 开发环境
├── staging.yaml          # 测试环境
└── production.yaml       # 生产环境

# 使用环境特定配置
export UNITY_SCANNER_CONFIG=config/development.yaml
uv run python -m src.cli.commands scan
```

#### 3. 扫描策略

```bash
# 首次完整扫描
uv run python -m src.cli.commands scan --full

# 日常增量扫描
uv run python -m src.cli.commands scan --incremental

# 特定功能开发时
uv run python -m src.cli.commands scan --path Assets/NewFeature/

# 发布前完整检查
uv run python -m src.cli.commands scan --full --detect-unused --detect-circular
```

### 性能优化建议

#### 1. 大型项目优化

对于超过10万文件的大型Unity项目：

```yaml
# config/large_project.yaml
performance:
  max_workers: 16
  batch_size: 2000
  memory_limit_mb: 8192
  
scan:
  exclude_paths:
    - "Assets/StreamingAssets/*"
    - "Assets/Archive/*"
    - "*.fbx.meta"  # 排除大型模型的meta文件
    
database:
  pool_size: 20
  cleanup_days: 7  # 更频繁的清理
```

#### 2. 网络存储优化

对于存储在网络驱动器上的项目：

```yaml
performance:
  network_timeout: 60
  retry_attempts: 5
  disk_buffer_size: 16384
  
scan:
  enable_checksum: false  # 禁用校验和以提升速度
  max_file_size_mb: 50   # 限制文件大小
```

#### 3. 内存优化

对于内存受限的环境：

```yaml
performance:
  memory_limit_mb: 1024
  batch_size: 500
  cache_size_mb: 64
  
features:
  experimental:
    deep_analysis: false  # 禁用深度分析
```

### 团队协作建议

#### 1. 集成到CI/CD流程

```yaml
# .github/workflows/unity-scan.yml
name: Unity Resource Scan
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install uv
        run: pip install uv
      - name: Install dependencies
        run: uv sync
      - name: Run Unity scan
        run: |
          uv run python -m src.cli.commands scan --incremental
          uv run python -m src.cli.commands detect-circular --report circular.md
      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: scan-reports
          path: reports/
```

#### 2. 代码审查集成

```bash
# pre-commit 钩子
#!/bin/bash
# .git/hooks/pre-commit

# 检查是否有Unity资源变更
git diff --cached --name-only | grep -E '\.(prefab|scene|asset)$' > /dev/null

if [ $? -eq 0 ]; then
    echo "检测到Unity资源变更，执行增量扫描..."
    uv run python -m src.cli.commands scan --incremental --quiet
    
    # 检查循环依赖
    uv run python -m src.cli.commands detect-circular --quiet
    if [ $? -ne 0 ]; then
        echo "❌ 发现循环依赖，请修复后再提交"
        exit 1
    fi
    
    echo "✅ 资源扫描通过"
fi
```

#### 3. 团队配置共享

```bash
# 团队配置模板
config/
├── team.yaml              # 团队通用配置
├── .env.template          # 环境变量模板
└── README.md             # 配置说明

# .env.template
UNITY_SCANNER_PROJECT_UNITY_PROJECT_PATH=/path/to/project
UNITY_SCANNER_PERFORMANCE_MAX_WORKERS=8
UNITY_SCANNER_OUTPUT_VERBOSITY=info
```

---

## 🚨 故障排除

### 常见问题和解决方案

#### 1. 安装和配置问题

**Q: `uv: command not found`**
```bash
# 解决方案：重新安装uv并添加到PATH
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # 或 ~/.zshrc
```

**Q: Python版本不兼容**
```bash
# 检查Python版本
python --version

# 使用uv管理Python版本
uv python install 3.11
uv python pin 3.11
```

**Q: 依赖安装失败**
```bash
# 清理缓存重新安装
uv cache clean
rm -rf .venv
uv sync --reinstall
```

#### 2. 扫描过程问题

**Q: 扫描速度过慢**
```bash
# 检查系统资源使用
uv run python -m src.cli.commands scan --profile

# 优化配置
export UNITY_SCANNER_PERFORMANCE_MAX_WORKERS=16
export UNITY_SCANNER_SCAN_BATCH_SIZE=2000
```

**Q: 内存不足错误**
```bash
# 限制内存使用
uv run python -m src.cli.commands scan --memory-limit 1GB

# 使用流式处理
uv run python -m src.cli.commands scan --streaming
```

**Q: 文件权限错误**
```bash
# 检查文件权限
ls -la /path/to/unity/project

# 修复权限问题
chmod -R 755 /path/to/unity/project
```

#### 3. 数据库问题

**Q: 数据库锁定错误**
```bash
# 检查数据库状态
uv run python -m src.cli.commands db-status

# 强制解锁
uv run python -m src.cli.commands db-unlock

# 重建数据库
uv run python -m src.cli.commands db-rebuild
```

**Q: 数据库损坏**
```bash
# 从备份恢复
uv run python -m src.cli.commands db-restore backup.db

# 重新扫描重建
rm unity_deps.db*
uv run python -m src.cli.commands scan --full
```

#### 4. 解析错误

**Q: Meta文件解析失败**
```bash
# 检查具体错误
uv run python -m src.cli.commands scan --verbose --debug

# 跳过错误文件继续扫描
uv run python -m src.cli.commands scan --ignore-errors
```

**Q: Unity版本不兼容**
```bash
# 检查支持的Unity版本
uv run python -m src.cli.commands --supported-unity-versions

# 强制兼容模式
uv run python -m src.cli.commands scan --force-compatibility
```

### 调试和日志

#### 启用详细日志

```bash
# 设置日志级别
export UNITY_SCANNER_OUTPUT_VERBOSITY=debug

# 启用文件日志
export UNITY_SCANNER_OUTPUT_LOG_FILE=debug.log

# 运行扫描
uv run python -m src.cli.commands scan --verbose
```

#### 性能分析

```bash
# 启用性能分析
uv run python -m src.cli.commands scan --profile --profile-output profile.json

# 分析性能报告
uv run python -c "
import json
with open('profile.json') as f:
    data = json.load(f)
    print(f'Total time: {data[\"total_time\"]:.2f}s')
    print(f'File parsing: {data[\"parsing_time\"]:.2f}s')
    print(f'Database ops: {data[\"db_time\"]:.2f}s')
"
```

#### 内存使用监控

```bash
# 启用内存监控
uv run python -m src.cli.commands scan --memory-monitor

# 生成内存使用报告
uv run python -m src.cli.commands scan --memory-report memory.json
```

---

## ⚡ 性能优化

### 系统级优化

#### 1. 硬件配置建议

| 项目规模 | CPU | 内存 | 存储 | 网络 |
|----------|-----|------|------|------|
| **小型** (<1万文件) | 4核 | 4GB | SSD | 本地 |
| **中型** (1-5万文件) | 8核 | 8GB | NVMe SSD | 千兆 |
| **大型** (5-20万文件) | 16核 | 16GB | 高速NVMe | 万兆 |
| **超大型** (>20万文件) | 32核 | 32GB | RAID NVMe | 专线 |

#### 2. 操作系统优化

**Linux/macOS**:
```bash
# 增加文件描述符限制
ulimit -n 65536
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 优化磁盘I/O调度
echo mq-deadline > /sys/block/sda/queue/scheduler

# 增加虚拟内存
sysctl vm.max_map_count=262144
```

**Windows**:
```powershell
# 增加虚拟内存
# 控制面板 → 系统 → 高级系统设置 → 性能设置 → 高级 → 虚拟内存

# 禁用Windows Defender实时监控 (针对项目目录)
Add-MpPreference -ExclusionPath "C:\Unity\Projects"
```

### 应用级优化

#### 1. 配置优化

```yaml
# config/performance.yaml
performance:
  # CPU密集型任务优化
  max_workers: 0  # 自动检测CPU核心数
  thread_pool_size: 32
  
  # 内存优化
  memory_limit_mb: 0  # 不限制内存
  batch_size: 5000
  cache_size_mb: 1024
  
  # I/O优化
  disk_buffer_size: 32768
  prefetch_size: 1000
  
  # 网络优化 (适用于网络存储)
  network_timeout: 120
  connection_pool_size: 20
  retry_backoff: 2.0

scan:
  # 并行扫描优化
  parallel_meta_parsing: true
  parallel_dependency_analysis: true
  
  # 缓存优化
  enable_file_cache: true
  cache_meta_content: true
  cache_guid_mappings: true
  
  # 跳过不必要的处理
  skip_unchanged_files: true
  skip_large_files_threshold_mb: 500
  
database:
  # 数据库性能优化
  journal_mode: "WAL"  # Write-Ahead Logging
  synchronous: "NORMAL"
  cache_size: -64000  # 64MB缓存
  temp_store: "MEMORY"
  
  # 批量操作优化
  batch_insert_size: 10000
  transaction_size: 50000
```

#### 2. 运行时优化

```bash
# 使用性能配置文件
export UNITY_SCANNER_CONFIG=config/performance.yaml

# 预分配系统资源
export MALLOC_ARENA_MAX=4
export OMP_NUM_THREADS=16

# 优化Python垃圾回收
export PYTHONHASHSEED=0
export PYTHONUNBUFFERED=1

# 运行扫描
uv run python -O -m src.cli.commands scan --performance-mode
```

### 特定场景优化

#### 1. 网络存储项目

```yaml
# config/network_storage.yaml
performance:
  network_timeout: 300
  retry_attempts: 10
  connection_pool_size: 50
  
scan:
  # 减少网络I/O
  enable_checksum: false
  cache_file_stats: true
  prefetch_meta_files: true
  
  # 批量处理
  batch_size: 1000
  meta_batch_size: 500
```

#### 2. 大型Prefab项目

```yaml
# config/large_prefabs.yaml
scan:
  # Prefab特殊处理
  prefab_deep_parse: false
  skip_nested_prefabs: true
  max_prefab_depth: 5
  
performance:
  # 针对大型YAML文件优化
  yaml_buffer_size: 65536
  streaming_yaml_parser: true
```

#### 3. 多版本Unity项目

```yaml
# config/multi_version.yaml
scan:
  # 版本兼容处理
  unity_version_detection: true
  backward_compatibility: true
  skip_version_conflicts: true
  
  # 路径优化
  version_specific_exclusions:
    "2019.4": ["Assets/2022Features/"]
    "2022.3": ["Assets/LegacyAssets/"]
```

### 监控和基准测试

#### 1. 性能基准测试

```bash
# 创建基准测试
uv run python -m src.cli.commands benchmark --create baseline

# 运行性能测试
uv run python -m src.cli.commands benchmark --run --compare baseline

# 生成性能报告
uv run python -m src.cli.commands benchmark --report performance.html
```

#### 2. 实时监控

```bash
# 启用实时监控
uv run python -m src.cli.commands scan --monitor --monitor-interval 5

# 监控输出示例
Monitor Report (Every 5s):
  CPU Usage: 85.3%
  Memory: 2.1GB / 16GB (13.1%)
  Disk I/O: Read 45MB/s, Write 12MB/s
  Files Processed: 12,345 / 50,000 (24.7%)
  Current Rate: 245 files/s
  ETA: 2min 35s
```

#### 3. 性能分析工具

```bash
# Python性能分析
uv run python -m cProfile -o profile.stats -m src.cli.commands scan
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"

# 内存分析
uv run python -m memory_profiler -m src.cli.commands scan --memory-profile

# 并发分析
uv run python -m src.cli.commands scan --concurrency-profile threads.json
```

---

这个详细的使用指南涵盖了Unity Resource Reference Scanner的所有核心功能和高级特性。用户可以根据自己的项目需求和技术水平，选择合适的使用方式。文档结构清晰，包含大量实用的代码示例和配置模板，能够帮助用户快速上手并充分利用工具的各种功能。