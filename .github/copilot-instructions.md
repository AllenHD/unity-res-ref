# Unity Resource Reference Scanner - AI Coding Guidelines

This project is a Python-based Unity asset dependency analyzer that scans `.meta` files to build resource reference graphs for large Unity projects.

## Architecture Overview

**Core Purpose**: Parse Unity project files (`.prefab`, `.scene`, `.asset`, etc.) by analyzing their `.meta` files to extract GUID dependencies and build a comprehensive resource dependency graph.

**Key Modules**:
- `src/core/` - Main scanning engine and dependency analysis logic
- `src/parsers/` - Unity file format parsers (meta files, asset serialization)
- `src/models/` - SQLAlchemy ORM models for resource relationships
- `src/cli/` - Typer-based CLI with Rich output formatting
- `src/utils/` - Shared utilities and helper functions
- `src/api/` - Optional REST API (FastAPI-based)

## Development Workflow

**Package Management**: Uses `uv` exclusively (NOT pip/poetry)
```bash
# Install dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Code quality
uv run black .
uv run ruff check --fix .
uv run mypy src/

# Run CLI
uv run python -m src.cli.commands
```

**Database**: SQLite with SQLAlchemy 2.0+ ORM for caching scan results and enabling incremental scans

## Project-Specific Patterns

**Configuration System**: Uses `config/default.yaml` with Pydantic validation
- Configurable scan paths: `Assets/`, `Packages/`
- Exclude patterns: `Library/`, `Temp/`, `StreamingAssets/`
- Performance tuning: batch sizes, worker threads, memory limits

**Incremental Scanning Logic**: Critical for large Unity projects
- Track file modification times vs last scan
- Use GUID-based dependency caching
- Implement change detection for `.meta` files only

**Unity-Specific Considerations**:
- GUID extraction from `.meta` files is the primary data source
- Handle Unity's asset serialization format (YAML-like but custom)
- Support for ScriptableObjects via C# script analysis
- Large file handling (50MB+ assets common in Unity)

## File Structure Conventions

**Module Organization**: Each `src/` subdirectory has `__init__.py` for clean imports
**CLI Entry Points**: Both `main.py` and `src.cli.commands:app` are configured
**Test Structure**: Mirrors `src/` with `unit/` and `integration/` separation

## Technology Stack Specifics

**Python 3.11+** requirement with modern async/await patterns
**SQLAlchemy 2.0+** declarative models with proper type hints
**Typer + Rich** for CLI with progress bars and colored output
**NetworkX** for dependency graph algorithms and cycle detection

## Development Status

Project is in early development phase:
- ✅ Basic architecture and tooling setup complete
- 🔄 Core scanning engine implementation in progress
- ❌ Unity file parsers not yet implemented
- ❌ Web API endpoints not yet implemented

When implementing new features, follow the established patterns in `config/default.yaml` for configuration options and ensure all new modules include proper `__init__.py` files for import consistency.
