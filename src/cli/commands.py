"""Unity Resource Reference Scanner - 命令行入口点

这是一个占位符文件，实际的CLI实现将在后续任务中完成。
"""

import typer

app = typer.Typer(
    name="unity-res-ref",
    help="Unity Resource Reference Scanner - 分析Unity项目资源依赖关系",
    no_args_is_help=True,
)


@app.command()
def hello() -> None:
    """测试命令 - 验证CLI框架工作正常"""
    typer.echo("Unity Resource Reference Scanner v0.1.0")
    typer.echo("项目基础架构已搭建完成!")


if __name__ == "__main__":
    app()
