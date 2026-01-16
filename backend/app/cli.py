"""v2t - 视频转文字工具"""

import asyncio
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.prompt import Prompt

from app.config import CONFIG_PATH, get_settings, load_config, save_config
from app.services.gitcode_ai import GitCodeAIError, generate_article, generate_outline
from app.services.transcribe import TranscribeError, extract_audio_async, transcribe_video
from app.services.video_downloader import DownloadError, download_video

console = Console()


def run_async(coro):
    """运行异步函数"""
    return asyncio.run(coro)


def get_output_name(title: str) -> str:
    """生成输出文件名"""
    name = title.replace("/", "_").replace("\\", "_")
    if len(name) > 50:
        name = name[:50]
    return name


def cleanup_file(path: Path):
    """安全删除文件"""
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass  # 忽略删除失败


def process_video(
    url: str,
    summary: bool = False,
    raw: bool = False,
    video_only: bool = False,
    audio_only: bool = False,
):
    """处理视频的核心逻辑"""
    settings = get_settings()
    current_dir = Path.cwd()

    # --video: 直接下载到当前目录
    if video_only:
        console.print("[bold]下载视频...[/bold]")
        try:
            video_result = run_async(download_video(url, output_dir=current_dir))
            console.print(f"[green]✓[/green] {video_result.title}")
            console.print(f"[green]✓[/green] 视频已保存: {video_result.path}")
        except DownloadError as e:
            console.print(f"[red]✗[/red] 下载失败: {e}")
            raise typer.Exit(1)
        return

    # --audio: 下载到临时目录，提取音频到当前目录
    if audio_only:
        console.print("[bold]下载视频...[/bold]")
        try:
            video_result = run_async(download_video(url))  # 下载到临时目录
            console.print(f"[green]✓[/green] {video_result.title}")
        except DownloadError as e:
            console.print(f"[red]✗[/red] 下载失败: {e}")
            raise typer.Exit(1)

        console.print("[bold]提取音频...[/bold]")
        output_name = get_output_name(video_result.title)
        audio_path = current_dir / f"{output_name}.mp3"
        try:
            run_async(extract_audio_async(video_result.path, audio_path))
            cleanup_file(video_result.path)  # 删除临时视频
            console.print(f"[green]✓[/green] 音频已保存: {audio_path}")
        except TranscribeError as e:
            cleanup_file(video_result.path)
            console.print(f"[red]✗[/red] 提取失败: {e}")
            raise typer.Exit(1)
        return

    # 正常流程：下载到临时目录，失败时保留临时文件
    temp_files = []  # 记录需要清理的临时文件

    # 1. 下载视频（已存在则跳过）
    console.print("[bold]下载视频...[/bold]")
    try:
        video_result = run_async(download_video(url))  # 下载到临时目录
        temp_files.append(video_result.path)
        console.print(f"[green]✓[/green] {video_result.title}")
    except DownloadError as e:
        console.print(f"[red]✗[/red] 下载失败: {e}")
        raise typer.Exit(1)

    # 检查视频时长
    if video_result.duration and video_result.duration > settings.max_video_duration:
        max_min = settings.max_video_duration // 60
        video_min = video_result.duration // 60
        console.print(
            f"[red]✗[/red] 视频时长 {video_min} 分钟，超过限制 {max_min} 分钟\n"
            f"可在配置文件中修改 max_video_duration: {CONFIG_PATH}"
        )
        raise typer.Exit(1)

    output_name = get_output_name(video_result.title)

    # 2. 转录（提取音频 + 转写，已存在则跳过提取）
    console.print("[bold]转录音频...[/bold]")
    try:
        transcript, audio_path = run_async(transcribe_video(video_result.path))
        temp_files.append(audio_path)
        console.print("[green]✓[/green] 转录完成")
    except TranscribeError as e:
        console.print(f"[red]✗[/red] 转录失败: {e}")
        raise typer.Exit(1)

    # 3. 根据选项处理，保存到当前目录
    if raw:
        output_path = Path(f"{output_name}.txt")
        output_path.write_text(transcript, encoding="utf-8")
        console.print(f"[green]✓[/green] 已保存: {output_path}")

    elif summary:
        console.print("[bold]生成提纲...[/bold]")
        try:
            outline = run_async(generate_outline(transcript))
            if not outline or len(outline.strip()) < 50:
                raise GitCodeAIError("内容被拦截或生成失败")
            output_path = Path(f"{output_name}_提纲.md")
            output_path.write_text(outline, encoding="utf-8")
            console.print(f"[green]✓[/green] 已保存: {output_path}")
        except GitCodeAIError as e:
            console.print(f"[yellow]⚠[/yellow] AI 生成失败: {e}")
            console.print("[yellow]⚠[/yellow] 回退到原始转录")
            output_path = Path(f"{output_name}.txt")
            output_path.write_text(transcript, encoding="utf-8")
            console.print(f"[green]✓[/green] 已保存: {output_path}")

    else:
        console.print("[bold]生成详细内容...[/bold]")
        try:
            article = run_async(generate_article(transcript))
            if not article or len(article.strip()) < 50:
                raise GitCodeAIError("内容被拦截或生成失败")
            output_path = Path(f"{output_name}.md")
            output_path.write_text(article, encoding="utf-8")
            console.print(f"[green]✓[/green] 已保存: {output_path}")
        except GitCodeAIError as e:
            console.print(f"[yellow]⚠[/yellow] AI 生成失败: {e}")
            console.print("[yellow]⚠[/yellow] 回退到原始转录")
            output_path = Path(f"{output_name}.txt")
            output_path.write_text(transcript, encoding="utf-8")
            console.print(f"[green]✓[/green] 已保存: {output_path}")

    # 4. 成功后清理临时文件
    for f in temp_files:
        cleanup_file(f)


# 主应用
app = typer.Typer(
    help="""v2t - 视频转文字工具

用法:
  v2t <url>             下载视频并生成 AI 总结 (.md)
  v2t <url> --summary   下载视频并生成提纲 (.md)
  v2t <url> --raw       下载视频并输出原始转录 (.txt)
  v2t <url> --video     仅下载视频
  v2t <url> --audio     仅提取音频
  v2t config            交互式配置 API KEY
  v2t clean             清理临时文件目录
""",
    add_completion=False,
    no_args_is_help=True,
)


def check_dependencies():
    """检查系统依赖，显示警告信息"""
    from app.deps import check_dependencies as check_deps
    from app.deps import get_install_hint

    missing = check_deps()
    if missing:
        console.print("[yellow]⚠ 缺少系统依赖:[/yellow]")
        for cmd, desc in missing:
            console.print(f"  • {cmd} ({desc})")
        console.print()
        console.print(get_install_hint())
        console.print()


@app.command("config")
def config_cmd():
    """交互式配置 API KEY"""
    check_dependencies()
    console.print("[bold]配置 API KEY[/bold]\n")

    config = load_config()

    console.print("[cyan]Groq API Key[/cyan] (用于语音转文字，必需)")
    console.print("获取地址: https://console.groq.com/keys")
    groq_key = Prompt.ask(
        "groq_api_key",
        default=config.get("groq_api_key", ""),
        show_default=bool(config.get("groq_api_key")),
    )

    console.print("\n[cyan]GitCode AI API Key[/cyan] (用于AI总结，必需)")
    console.print("获取地址: https://ai.gitcode.com/")
    gitcode_key = Prompt.ask(
        "gitcode_ai_token",
        default=config.get("gitcode_ai_token", ""),
        show_default=bool(config.get("gitcode_ai_token")),
    )

    console.print("\n[cyan]Xiazaitool Token[/cyan] (备用下载，可选)")
    xiazai_key = Prompt.ask(
        "xiazaitool_token",
        default=config.get("xiazaitool_token", ""),
        show_default=bool(config.get("xiazaitool_token")),
    )

    config["groq_api_key"] = groq_key
    config["gitcode_ai_token"] = gitcode_key
    if xiazai_key:
        config["xiazaitool_token"] = xiazai_key

    save_config(config)
    console.print(f"\n[green]✓[/green] 配置已保存到 {CONFIG_PATH}")


@app.command("clean")
def clean_cmd():
    """清理临时文件目录"""
    import shutil
    settings = get_settings()
    temp_path = settings.temp_path

    if not temp_path.exists():
        console.print(f"[yellow]临时目录不存在: {temp_path}[/yellow]")
        return

    # 统计文件数量和大小
    files = list(temp_path.iterdir())
    if not files:
        console.print(f"[yellow]临时目录为空: {temp_path}[/yellow]")
        return

    total_size = sum(f.stat().st_size for f in files if f.is_file())
    size_mb = total_size / (1024 * 1024)

    # 删除目录内容
    for item in files:
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)

    console.print(f"[green]✓[/green] 已清理 {len(files)} 个文件 ({size_mb:.1f} MB)")
    console.print(f"[dim]临时目录: {temp_path}[/dim]")


@app.command("run", hidden=True)
def run_cmd(
    url: Annotated[str, typer.Argument(help="视频链接")],
    summary: Annotated[bool, typer.Option("--summary", "-s", help="生成提纲")] = False,
    raw: Annotated[bool, typer.Option("--raw", "-r", help="输出原始转录")] = False,
    video: Annotated[bool, typer.Option("--video", "-v", help="仅下载视频")] = False,
    audio: Annotated[bool, typer.Option("--audio", "-a", help="仅提取音频")] = False,
):
    """处理视频链接"""
    process_video(url, summary, raw, video, audio)


def main():
    """入口函数 - 处理默认命令"""
    args = sys.argv[1:]

    # 如果没有参数，显示帮助
    if not args:
        app()
        return

    # 如果第一个参数是已知子命令，正常处理
    if args[0] in ("config", "clean", "--help", "-h"):
        app()
        return

    # 否则，假设是 URL，插入 "run" 命令
    sys.argv = [sys.argv[0], "run"] + args
    app()


if __name__ == "__main__":
    main()
