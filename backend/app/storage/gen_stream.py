"""Redis Stream 作为生成任务的可重读缓冲

每个生成任务一条 stream（key = `gen:{task_id}`），worker XADD chunk/事件，
SSE 端点用 XREAD BLOCK 拿历史 + 阻塞等新消息——同一个原语完成"回放 + 跟读"。

Entry payload schema（用 `type` 字段区分）：
  - {type: "chunk",        text: "..."}
  - {type: "script_done"}                              # podcast 脚本流结束
  - {type: "synthesizing"}                             # podcast TTS 开始
  - {type: "done",         resource_id?: "..."}         # 文本类
  - {type: "done",         has_audio: "1"|"0",
                           audio_resource_id?: "...",
                           audio_error?: "..."}        # podcast
  - {type: "error",        message: "..."}

完成或失败后 EXPIRE 1h，给迟到的续传留窗口；未完成的不设 EXPIRE 防丢。
"""

from redis.asyncio import Redis

STREAM_MAXLEN = 10000  # 防 LLM 极端长输出撑爆 Redis；一次生成 chunk 数典型 < 1k
STREAM_TTL_AFTER_END = 3600  # 终结后保留 1h，覆盖刷新续传窗口


def gen_stream_key(task_id: str) -> str:
    return f"gen:{task_id}"


async def xadd_event(
    redis: Redis, task_id: str, event: dict[str, str]
) -> str:
    """追加一条事件到生成 stream，返回 entry id（用于 SSE Last-Event-ID）。"""
    return await redis.xadd(
        gen_stream_key(task_id),
        event,
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )


async def xadd_chunk(redis: Redis, task_id: str, text: str) -> str:
    return await xadd_event(redis, task_id, {"type": "chunk", "text": text})


async def finalize_stream(redis: Redis, task_id: str) -> None:
    """终结后给 stream 设过期。done/error 后调用一次。"""
    await redis.expire(gen_stream_key(task_id), STREAM_TTL_AFTER_END)


async def xadd_done_and_finalize(
    redis: Redis, task_id: str, payload: dict[str, str]
) -> str:
    """写 done sentinel 并 EXPIRE，保证终结+过期是同一段流程。"""
    entry = {"type": "done", **payload}
    entry_id = await xadd_event(redis, task_id, entry)
    await finalize_stream(redis, task_id)
    return entry_id


async def xadd_error_and_finalize(
    redis: Redis, task_id: str, message: str
) -> str:
    entry_id = await xadd_event(redis, task_id, {"type": "error", "message": message})
    await finalize_stream(redis, task_id)
    return entry_id


async def read_stream(
    redis: Redis,
    task_id: str,
    last_id: str,
    *,
    block_ms: int,
    count: int = 200,
) -> list[tuple[str, dict[str, str]]]:
    """从 last_id 之后读取若干 entry。

    block_ms=0 时立即返回当前可用 entry（没有则空 list）；> 0 时无新消息会
    阻塞至超时返回空 list。SSE 端点用一个循环 + block_ms=30000 同时完成
    "回放已有"和"跟读新消息"——XREAD 不区分 entry 是不是已经在 stream 里。

    last_id 用 "0" 表示从头读，"$" 表示只看新消息。

    decode_responses=True 已开，返回 dict[str,str]。
    """
    result = await redis.xread(
        {gen_stream_key(task_id): last_id},
        count=count,
        block=block_ms,
    )
    if not result:
        return []
    # result 形如 [(stream_name, [(id, {field: value}), ...])]
    _, entries = result[0]
    return entries
