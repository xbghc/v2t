"""诊断 / 联调测试路由

为运维与开发提供一组独立于业务流的轻量端点：
    GET  /api/diag/         单页 HTML，浏览器直接打开就能用
    GET  /api/diag/health   并发探测 Redis / Xiazaitool / LLM / Whisper / DashScope STT / TTS
    POST /api/diag/parse    {url} → 路由到对应 downloader provider，只解析不下载
    POST /api/diag/llm      {prompt} → 单轮 chat_complete
    POST /api/diag/stt      multipart audio → transcribe_audio

不写业务侧逻辑，只是把已有 check / 解析 / 转录函数包一层 timing + 错误归一。
"""

import asyncio
import logging
import tempfile
import time
from collections.abc import Awaitable
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/diag", tags=["diagnostics"])


# ============ 通用 ============

async def _timed(coro: Awaitable[tuple[bool, str]]) -> tuple[bool, str, int]:
    t = time.monotonic()
    ok, msg = await coro
    return ok, msg, int((time.monotonic() - t) * 1000)


def _timed_sync(fn) -> tuple[bool, str, int]:
    t = time.monotonic()
    ok, msg = fn()
    return ok, msg, int((time.monotonic() - t) * 1000)


# ============ /health ============

class HealthItem(BaseModel):
    name: str
    ok: bool
    message: str
    latency_ms: int


class HealthResponse(BaseModel):
    results: list[HealthItem]


async def _check_redis() -> tuple[bool, str]:
    from app.config import get_settings
    from app.storage import get_metadata_store

    settings = get_settings()
    if not settings.redis_url:
        return False, "未配置 REDIS_URL"
    return await get_metadata_store().check_connection()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """并发探测所有外部依赖"""
    from app.services.dashscope_stt import check_dashscope_stt
    from app.services.llm import check_llm_api
    from app.services.podcast_tts import check_tts_api
    from app.services.transcribe import check_whisper_api
    from app.services.xiazaitool import check_xiazaitool_token

    async_checks: list[tuple[str, Awaitable[tuple[bool, str]]]] = [
        ("Redis", _check_redis()),
        ("LLM", check_llm_api()),
        ("Whisper", check_whisper_api()),
        ("DashScope STT", check_dashscope_stt()),
        ("TTS", check_tts_api()),
    ]

    timed = await asyncio.gather(*[_timed(c) for _, c in async_checks])
    items = [
        HealthItem(name=n, ok=ok, message=msg, latency_ms=ms)
        for (n, _), (ok, msg, ms) in zip(async_checks, timed, strict=True)
    ]

    sync_ok, sync_msg, sync_ms = _timed_sync(check_xiazaitool_token)
    items.insert(
        1,
        HealthItem(
            name="Xiazaitool Token",
            ok=sync_ok,
            message=sync_msg,
            latency_ms=sync_ms,
        ),
    )

    return HealthResponse(results=items)


# ============ /parse ============

class ParseRequest(BaseModel):
    url: str


class ParseResponse(BaseModel):
    ok: bool
    provider: str
    latency_ms: int
    title: str | None = None
    duration: int | None = None
    cover_url: str | None = None
    video_url: str | None = None
    error: str | None = None


def _ytdlp_extract(url: str) -> dict:
    import yt_dlp

    from app.config import get_settings

    proxy = get_settings().effective_proxy
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    if proxy:
        opts["proxy"] = proxy
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info or {}


@router.post("/parse", response_model=ParseResponse)
async def parse(req: ParseRequest) -> ParseResponse:
    """路由到对应 provider 解析视频，不实际下载"""
    from app.services.downloader import select_provider
    from app.services.downloader.base import DownloadError
    from app.utils.url_hash import normalize_url

    # 与 download_video 保持一致：先剥 tracking 参数再交给 provider
    url = normalize_url(req.url)

    try:
        provider = select_provider(url)
    except DownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    t = time.monotonic()

    if provider.name == "yt-dlp":
        try:
            info = await asyncio.to_thread(_ytdlp_extract, url)
        except Exception as e:
            return ParseResponse(
                ok=False,
                provider=provider.name,
                latency_ms=int((time.monotonic() - t) * 1000),
                error=f"{type(e).__name__}: {e}",
            )
        return ParseResponse(
            ok=True,
            provider=provider.name,
            latency_ms=int((time.monotonic() - t) * 1000),
            title=(info.get("title") or "").strip() or None,
            duration=int(info["duration"])
            if isinstance(info.get("duration"), int | float)
            else None,
            cover_url=info.get("thumbnail") or None,
            video_url=info.get("webpage_url") or url,
        )

    if provider.name == "xiazaitool":
        from app.services.xiazaitool import XiazaitoolError, parse_video_url

        try:
            v = await parse_video_url(url)
        except XiazaitoolError as e:
            return ParseResponse(
                ok=False,
                provider=provider.name,
                latency_ms=int((time.monotonic() - t) * 1000),
                error=str(e),
            )
        except Exception as e:
            return ParseResponse(
                ok=False,
                provider=provider.name,
                latency_ms=int((time.monotonic() - t) * 1000),
                error=f"{type(e).__name__}: {e}",
            )
        return ParseResponse(
            ok=True,
            provider=provider.name,
            latency_ms=int((time.monotonic() - t) * 1000),
            title=v.title or None,
            cover_url=v.cover_url or None,
            video_url=v.video_url or None,
        )

    raise HTTPException(
        status_code=500, detail=f"未知 provider: {provider.name}"
    )


# ============ /llm ============

class LLMRequest(BaseModel):
    prompt: str
    max_tokens: int = 512


class LLMResponse(BaseModel):
    ok: bool
    latency_ms: int
    response: str | None = None
    error: str | None = None


@router.post("/llm", response_model=LLMResponse)
async def llm(req: LLMRequest) -> LLMResponse:
    from app.services.llm import chat_complete

    t = time.monotonic()
    try:
        text = await chat_complete(
            messages=[{"role": "user", "content": req.prompt}],
            max_tokens=req.max_tokens,
        )
    except Exception as e:
        return LLMResponse(
            ok=False,
            latency_ms=int((time.monotonic() - t) * 1000),
            error=f"{type(e).__name__}: {e}",
        )
    return LLMResponse(
        ok=True,
        latency_ms=int((time.monotonic() - t) * 1000),
        response=text,
    )


# ============ /stt ============

class STTResponse(BaseModel):
    ok: bool
    latency_ms: int
    text: str | None = None
    error: str | None = None


@router.post("/stt", response_model=STTResponse)
async def stt(audio: UploadFile = File(...)) -> STTResponse:
    from app.services.transcribe import transcribe_audio

    t = time.monotonic()
    suffix = Path(audio.filename or "").suffix or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(await audio.read())
        tmp_path = Path(f.name)
    try:
        text = await transcribe_audio(tmp_path)
    except Exception as e:
        return STTResponse(
            ok=False,
            latency_ms=int((time.monotonic() - t) * 1000),
            error=f"{type(e).__name__}: {e}",
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return STTResponse(
        ok=True,
        latency_ms=int((time.monotonic() - t) * 1000),
        text=text,
    )


# ============ /  HTML 测试页 ============

_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>v2t 服务诊断</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 14px/1.5 -apple-system, system-ui, sans-serif; max-width: 900px; margin: 24px auto; padding: 0 16px; }
  h1 { font-size: 20px; margin: 0 0 16px; }
  h2 { font-size: 15px; margin: 20px 0 8px; padding-top: 8px; border-top: 1px solid #ccc4; }
  button { font: inherit; padding: 6px 14px; border-radius: 6px; border: 1px solid #888; background: #fff2; cursor: pointer; }
  button:hover:not(:disabled) { background: #88f3; }
  button:disabled { opacity: .5; cursor: not-allowed; }
  textarea, input[type=text] { width: 100%; box-sizing: border-box; font: inherit; padding: 6px 8px; border: 1px solid #888; border-radius: 4px; background: transparent; color: inherit; }
  textarea { min-height: 70px; resize: vertical; }
  .row { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
  .row > input { flex: 1; }
  .out { margin-top: 8px; padding: 8px 10px; border-radius: 4px; background: #8881; white-space: pre-wrap; word-wrap: break-word; min-height: 1.5em; font-family: ui-monospace, Consolas, monospace; font-size: 13px; }
  .ok { color: #0a0; }
  .bad { color: #c00; }
  .muted { color: #888; }
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #8884; }
  th { font-weight: 600; }
</style>
</head>
<body>
<h1>v2t 服务诊断</h1>

<h2>1. 连通性 <button id="btnHealth">全部检查</button></h2>
<div id="healthOut" class="out muted">点击按钮开始</div>

<h2>2. 视频链接解析（不下载）</h2>
<div class="row">
  <input id="parseUrl" type="text" placeholder="https://www.bilibili.com/video/BV... 或 youtube.com/..." />
  <button id="btnParse">解析</button>
</div>
<div id="parseOut" class="out muted">输入链接后点击解析</div>

<h2>3. LLM 单轮对话</h2>
<textarea id="llmPrompt" placeholder="问点什么...">用一句话介绍你自己</textarea>
<div class="row"><button id="btnLlm">发送</button><span class="muted" id="llmHint"></span></div>
<div id="llmOut" class="out muted">等待发送</div>

<h2>4. STT 转录（上传短音频）</h2>
<div class="row">
  <input id="sttFile" type="file" accept="audio/*,video/*" />
  <button id="btnStt">转录</button>
</div>
<div id="sttOut" class="out muted">选择音频后点击转录</div>

<script>
function fmtErr(e) { return (e && e.message) ? e.message : String(e); }
function setBusy(btn, busy, label) { btn.disabled = busy; btn.textContent = busy ? (label || '处理中...') : (btn.dataset.label); }

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || ('HTTP ' + r.status));
  return data;
}

// 1. health
document.getElementById('btnHealth').dataset.label = '全部检查';
document.getElementById('btnHealth').addEventListener('click', async () => {
  const btn = document.getElementById('btnHealth');
  const out = document.getElementById('healthOut');
  setBusy(btn, true, '探测中...');
  out.textContent = '探测中...';
  out.className = 'out muted';
  try {
    const r = await fetch('/api/diag/health');
    const data = await r.json();
    let html = '<table><thead><tr><th>服务</th><th>状态</th><th>耗时</th><th>消息</th></tr></thead><tbody>';
    for (const it of data.results) {
      const cls = it.ok ? 'ok' : 'bad';
      const flag = it.ok ? '✓' : '✗';
      html += `<tr><td>${it.name}</td><td class="${cls}">${flag}</td><td>${it.latency_ms}ms</td><td>${escapeHtml(it.message)}</td></tr>`;
    }
    html += '</tbody></table>';
    out.innerHTML = html;
    out.className = 'out';
  } catch (e) {
    out.textContent = '✗ ' + fmtErr(e);
    out.className = 'out bad';
  } finally {
    setBusy(btn, false);
  }
});

// 2. parse
document.getElementById('btnParse').dataset.label = '解析';
document.getElementById('btnParse').addEventListener('click', async () => {
  const btn = document.getElementById('btnParse');
  const out = document.getElementById('parseOut');
  const url = document.getElementById('parseUrl').value.trim();
  if (!url) { out.textContent = '请输入链接'; out.className = 'out bad'; return; }
  setBusy(btn, true, '解析中...');
  out.textContent = '解析中...';
  out.className = 'out muted';
  try {
    const data = await postJSON('/api/diag/parse', { url });
    const lines = [
      `provider: ${data.provider}`,
      `状态: ${data.ok ? '✓ OK' : '✗ FAIL'}`,
      `耗时: ${data.latency_ms}ms`,
    ];
    if (data.ok) {
      if (data.title) lines.push(`标题: ${data.title}`);
      if (data.duration != null) lines.push(`时长: ${data.duration}s`);
      if (data.cover_url) lines.push(`封面: ${data.cover_url}`);
      if (data.video_url) lines.push(`链接: ${data.video_url}`);
    } else {
      lines.push(`错误: ${data.error}`);
    }
    out.textContent = lines.join('\\n');
    out.className = 'out ' + (data.ok ? 'ok' : 'bad');
  } catch (e) {
    out.textContent = '✗ ' + fmtErr(e);
    out.className = 'out bad';
  } finally {
    setBusy(btn, false);
  }
});

// 3. llm
document.getElementById('btnLlm').dataset.label = '发送';
document.getElementById('btnLlm').addEventListener('click', async () => {
  const btn = document.getElementById('btnLlm');
  const out = document.getElementById('llmOut');
  const hint = document.getElementById('llmHint');
  const prompt = document.getElementById('llmPrompt').value.trim();
  if (!prompt) { out.textContent = '请输入提示词'; out.className = 'out bad'; return; }
  setBusy(btn, true, '生成中...');
  out.textContent = '生成中...';
  out.className = 'out muted';
  hint.textContent = '';
  try {
    const data = await postJSON('/api/diag/llm', { prompt, max_tokens: 512 });
    if (data.ok) {
      out.textContent = data.response;
      out.className = 'out';
    } else {
      out.textContent = '✗ ' + data.error;
      out.className = 'out bad';
    }
    hint.textContent = `${data.latency_ms}ms`;
  } catch (e) {
    out.textContent = '✗ ' + fmtErr(e);
    out.className = 'out bad';
  } finally {
    setBusy(btn, false);
  }
});

// 4. stt
document.getElementById('btnStt').dataset.label = '转录';
document.getElementById('btnStt').addEventListener('click', async () => {
  const btn = document.getElementById('btnStt');
  const out = document.getElementById('sttOut');
  const file = document.getElementById('sttFile').files[0];
  if (!file) { out.textContent = '请选择音频文件'; out.className = 'out bad'; return; }
  setBusy(btn, true, '转录中（可能需要数十秒）...');
  out.textContent = '上传 + 转录中...';
  out.className = 'out muted';
  try {
    const fd = new FormData();
    fd.append('audio', file);
    const r = await fetch('/api/diag/stt', { method: 'POST', body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || ('HTTP ' + r.status));
    if (data.ok) {
      out.textContent = `[${data.latency_ms}ms]\\n` + data.text;
      out.className = 'out';
    } else {
      out.textContent = `[${data.latency_ms}ms] ✗ ${data.error}`;
      out.className = 'out bad';
    }
  } catch (e) {
    out.textContent = '✗ ' + fmtErr(e);
    out.className = 'out bad';
  } finally {
    setBusy(btn, false);
  }
});

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
</script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def page() -> HTMLResponse:
    return HTMLResponse(content=_HTML)
