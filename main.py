"""Unity Resource Reference Scanner - 主入口点

这是项目的主入口点，导入并运行CLI应用。
"""

from src.cli.commands import app


def main() -> None:
    """主函数 - 启动CLI应用"""
    app()


if __name__ == "__main__":
    main()
