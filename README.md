# Unity Resource Reference Scanner

Unity项目资源引用关系扫描工具，基于Python开发，支持分析Unity项目中的资源依赖关系。

## 功能特性

- 🔍 扫描Unity项目资源文件（.prefab、.scene、.asset等）
- 📋 解析.meta文件提取GUID和依赖信息
- 🗄️ 使用SQLite数据库缓存，支持增量扫描
- ⚡ 高性能并发处理，支持大型项目
- 📊 多种导出格式（JSON、CSV、DOT图形）
- 🎯 检测未使用资源和循环依赖
- 🛠️ 配置化扫描路径和排除规则

## 技术栈

- **语言**: Python 3.11+
- **包管理**: uv
- **数据库**: SQLite + SQLAlchemy ORM
- **配置**: YAML + Pydantic验证
- **CLI**: Typer + Rich美化输出
- **测试**: pytest + coverage
- **代码质量**: black + ruff + mypy

## 开发环境设置

### 前置要求

- Python 3.11+
- uv包管理工具

### 安装uv（如果还未安装）

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用pip
pip install uv
```

### 项目设置

```bash
# 克隆项目
git clone <repository-url>
cd unity-res-ref

# 安装依赖
uv sync

# 安装开发依赖
uv sync --extra dev

# 运行测试
uv run pytest

# 代码格式化
uv run black .
uv run ruff check --fix .

# 运行CLI
uv run python -m src.cli.commands
```

## 项目结构

```
unity-res-ref/
├── src/                    # 源代码
│   ├── core/              # 核心功能模块
│   ├── parsers/           # 文件解析器
│   ├── models/            # 数据模型
│   ├── utils/             # 工具函数
│   ├── cli/               # 命令行界面
│   └── api/               # REST API（可选）
├── config/                # 配置文件
├── tests/                 # 测试代码
│   ├── unit/             # 单元测试
│   ├── integration/      # 集成测试
│   └── fixtures/         # 测试数据
├── docs/                  # 文档
├── pyproject.toml         # 项目配置
└── README.md             # 项目说明
```

## 开发状态

项目当前处于开发阶段，基础架构已完成：

- ✅ 项目结构搭建
- ✅ 开发环境配置
- ✅ 包管理和依赖安装
- ✅ 代码质量工具配置
- ✅ 测试框架设置
- 🔄 核心功能开发中...

## 技术文档

详细的技术设计文档请参考：[TECHNICAL_DESIGN.md](./TECHNICAL_DESIGN.md)

## 开发日志

项目开发过程的详细记录请参考：[开发日志目录](./dev_log/)

- 📋 [开发日志索引](./dev_log/README.md) - 查看所有任务完成记录
- 📝 [任务一：项目基础架构搭建](./dev_log/task_01_project_setup.md) - 2025-07-31 完成

## 贡献指南

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开Pull Request

## 许可证

待定

## 联系方式

项目维护者：Unity Resource Reference Scanner Team
