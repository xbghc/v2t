"""v2t - 视频转文字工具"""

import asyncio
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.prompt import Prompt

from app.config import load_config, save_config, get_settings, CONFIG_PATH
from app.services.video_downloader import download_video, DownloadError
from app.services.transcribe import transcribe_video, extract_audio, TranscribeError
from app.services.gitcode_ai import generate_outline, generate_article, GitCodeAIError

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


def process_video(
    url: str,
    summary: bool = False,
    raw: bool = False,
    video_only: bool = False,
    audio_only: bool = False,
):
    """处理视频的核心逻辑"""
    settings = get_settings()

    # 1. 下载视频
    console.print("[bold]下载视频...[/bold]")
    try:
        video_result = run_async(download_video(url))
        console.print(f"[green]✓[/green] {video_result.title}")
    except DownloadError as e:
        console.print(f"[red]✗[/red] 下载失败: {e}")
        raise typer.Exit(1)

    # 仅下载视频
    if video_only:
        console.print(f"[green]✓[/green] 视频已保存: {video_result.path}")
        return

    # 仅提取音频
    if audio_only:
        audio_path = extract_audio(video_result.path)
        console.print(f"[green]✓[/green] 音频已保存: {audio_path}")
        return

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

    # 2. 转录
    console.print("[bold]转录音频...[/bold]")
    try:
        transcript = run_async(transcribe_video(video_result.path))
        console.print("[green]✓[/green] 转录完成")
    except TranscribeError as e:
        console.print(f"[red]✗[/red] 转录失败: {e}")
        raise typer.Exit(1)

    # 3. 根据选项处理
    if raw:
        output_path = Path(f"{output_name}.txt")
        output_path.write_text(transcript, encoding="utf-8")
        console.print(f"[green]✓[/green] 已保存: {output_path}")

    elif summary:
        console.print("[bold]生成提纲...[/bold]")
        try:
            outline = run_async(generate_outline(transcript))
            output_path = Path(f"{output_name}_提纲.md")
            output_path.write_text(outline, encoding="utf-8")
            console.print(f"[green]✓[/green] 已保存: {output_path}")
        except GitCodeAIError as e:
            console.print(f"[red]✗[/red] 生成失败: {e}")
            raise typer.Exit(1)

    else:
        console.print("[bold]生成详细内容...[/bold]")
        try:
            article = run_async(generate_article(transcript))
            output_path = Path(f"{output_name}.md")
            output_path.write_text(article, encoding="utf-8")
            console.print(f"[green]✓[/green] 已保存: {output_path}")
        except GitCodeAIError as e:
            console.print(f"[red]✗[/red] 生成失败: {e}")
            raise typer.Exit(1)


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
""",
    add_completion=False,
    no_args_is_help=True,
)


@app.command("config")
def config_cmd():
    """交互式配置 API KEY"""
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
    if args[0] in ("config", "--help", "-h"):
        app()
        return

    # 否则，假设是 URL，插入 "run" 命令
    sys.argv = [sys.argv[0], "run"] + args
    app()


if __name__ == "__main__":
    main()
