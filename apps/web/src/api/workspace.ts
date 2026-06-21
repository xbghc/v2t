import { fetchEventSource } from '@microsoft/fetch-event-source'
import type {
    GenerationContentType,
    GenerationTaskResponse,
    PromptsResponse,
    WorkspaceResponse,
    StreamPrompts,
    BilibiliVideoMetaResponse,
    WorkspaceLookupResponse,
    StatusStreamEvent,
    TranscriptSegmentMessage,
} from '@/types'

// API 基础路径，使用 Vite 的 base 配置。
// 对外接口统一走 /api/v1（与后端 constants.API_V1_PREFIX 对应）；
// 内部端点 /api/admin、/api/metrics 由各自模块保留 /api，不加 v1。
export const API_BASE = `${import.meta.env.BASE_URL}api/v1`

/**
 * 获取默认提示词
 */
export async function getDefaultPrompts(): Promise<PromptsResponse> {
    const response = await fetch(`${API_BASE}/prompts`)
    if (!response.ok) {
        throw new Error('获取默认提示词失败')
    }
    return response.json() as Promise<PromptsResponse>
}

/**
 * 创建工作区
 */
export async function createWorkspace(
    url: string,
    options?: { seriesBvid?: string; seriesIndex?: number }
): Promise<WorkspaceResponse> {
    const body: Record<string, unknown> = { url }
    if (options?.seriesBvid && options.seriesIndex && options.seriesIndex > 0) {
        body.series_bvid = options.seriesBvid
        body.series_index = options.seriesIndex
    }
    const response = await fetch(`${API_BASE}/workspaces`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
    const data = await response.json() as WorkspaceResponse | { detail: string }

    if (!response.ok) {
        throw new Error((data as { detail: string }).detail || '创建工作区失败')
    }

    return data as WorkspaceResponse
}

/**
 * 探测 B 站视频的分 P 列表
 * 失败时返回 null（用户输入的 URL 不是 B 站 / 不含 BV / 调用失败都视为"不可探测"）
 */
export async function fetchBilibiliPages(
    url: string
): Promise<BilibiliVideoMetaResponse | null> {
    try {
        const response = await fetch(
            `${API_BASE}/bilibili/pages?url=${encodeURIComponent(url)}`
        )
        if (!response.ok) return null
        return await response.json() as BilibiliVideoMetaResponse
    } catch {
        return null
    }
}

/**
 * 查询某 BV + 分 P 是否已有对应的 workspace
 */
export async function lookupWorkspaceBySeries(
    seriesBvid: string,
    seriesIndex: number
): Promise<string | null> {
    try {
        const response = await fetch(
            `${API_BASE}/workspaces/lookup?series_bvid=${encodeURIComponent(seriesBvid)}&series_index=${seriesIndex}`
        )
        if (!response.ok) return null
        const data = await response.json() as WorkspaceLookupResponse
        return data.workspace_id
    } catch {
        return null
    }
}

/**
 * 获取工作区信息
 */
export async function getWorkspace(workspaceId: string): Promise<WorkspaceResponse> {
    const response = await fetch(`${API_BASE}/workspaces/${workspaceId}`)
    if (!response.ok) {
        const data = await response.json() as { detail?: string }
        throw new Error(data.detail || '获取工作区失败')
    }
    return response.json() as Promise<WorkspaceResponse>
}

/**
 * SSE 流式监听工作区状态变化
 *
 * SSE envelope 区分两种事件：
 *   - type=workspace        全量 WorkspaceResponse
 *   - type=transcript.append 单段转录增量
 *
 * @param onTranscriptSegment 可选；若不传，转录增量事件被静默丢弃
 * @returns 清理函数
 */
export function streamWorkspaceStatus(
    workspaceId: string,
    onStatusChange: (data: WorkspaceResponse) => void,
    onError: (error: string) => void,
    onTranscriptSegment?: (segment: TranscriptSegmentMessage) => void,
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`${API_BASE}/workspaces/${workspaceId}/status-stream`, {
        signal: ctrl.signal,
        openWhenHidden: true,
        async onopen(response) {
            if (response.ok && response.headers.get('content-type')?.includes('text/event-stream')) {
                return
            }
            const contentType = response.headers.get('content-type')
            if (contentType?.includes('application/json')) {
                const data = await response.json() as { detail?: string }
                throw new Error(data.detail || `HTTP ${response.status}`)
            }
            throw new Error(`HTTP ${response.status}`)
        },
        onmessage(ev) {
            if (!ev.data) return
            const envelope = JSON.parse(ev.data) as StatusStreamEvent
            if (envelope.type === 'workspace') {
                onStatusChange(envelope.data)
                if (envelope.data.status === 'failed' || envelope.data.status === 'ready') {
                    ctrl.abort()
                }
            } else if (envelope.type === 'transcript.append') {
                onTranscriptSegment?.(envelope.data)
            }
        },
        onerror(err) {
            onError(err instanceof Error ? err.message : '连接错误')
            throw err
        },
        onclose() {
            // SSE 连接正常关闭
        },
    })

    return () => ctrl.abort()
}

/**
 * 启动一次内容生成（幂等：已有活跃 task 直接复用，不重新调 LLM）
 */
export async function startGeneration(
    workspaceId: string,
    contentType: GenerationContentType,
    prompts: StreamPrompts
): Promise<GenerationTaskResponse> {
    const response = await fetch(
        `${API_BASE}/workspaces/${workspaceId}/stream/${contentType}`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                system_prompt: prompts.systemPrompt,
                user_prompt: prompts.userPrompt,
            }),
        }
    )
    const data = await response.json() as GenerationTaskResponse | { detail: string }
    if (!response.ok) {
        throw new Error((data as { detail: string }).detail || '启动生成失败')
    }
    return data as GenerationTaskResponse
}

/**
 * 消费一个生成任务的 SSE 流
 *
 * fetchEventSource 默认在网络断开时会自动重连，并自动携带 Last-Event-ID，
 * server 端按该 id 续推——即"底层断网无感续传"由协议层处理。
 *
 * 终结 sentinel：业务侧的 done / error 事件触发 cleanup（abort 控制器），
 * fetchEventSource 收到后不会重连。永远不依赖"连接关闭"判断结束。
 *
 * @returns 清理函数（手动断开连接）
 */
export interface GenerationStreamCallbacks {
    onChunk: (text: string) => void
    onScriptDone?: () => void
    onSynthesizing?: () => void
    onDone: (payload: {
        resourceId?: string
        hasAudio?: boolean
        audioResourceId?: string
        audioError?: string
    }) => void
    onError: (message: string) => void
}

interface GenerationStreamEvent {
    type: 'chunk' | 'script_done' | 'synthesizing' | 'done' | 'error'
    text?: string
    resource_id?: string
    has_audio?: string  // "1" / "0"
    audio_resource_id?: string
    audio_error?: string
    message?: string
}

export function consumeGenerationStream(
    streamUrl: string,
    callbacks: GenerationStreamCallbacks
): () => void {
    const ctrl = new AbortController()
    let closedByBusiness = false

    fetchEventSource(streamUrl, {
        signal: ctrl.signal,
        openWhenHidden: true,
        async onopen(response) {
            if (response.ok && response.headers.get('content-type')?.includes('text/event-stream')) {
                return
            }
            // 4xx → 永久错误，停止重连（任务不存在、workspace 过期等）
            if (response.status >= 400 && response.status < 500) {
                let detail = `HTTP ${response.status}`
                try {
                    const data = await response.json() as { detail?: string }
                    if (data.detail) detail = data.detail
                } catch {
                    // 忽略 JSON 解析失败
                }
                callbacks.onError(detail)
                closedByBusiness = true
                ctrl.abort()
                throw new Error(detail)
            }
            // 5xx：抛非 FatalError，触发 fetchEventSource 自动重试
            throw new Error(`HTTP ${response.status}`)
        },
        onmessage(ev) {
            if (!ev.data) return
            const data = JSON.parse(ev.data) as GenerationStreamEvent
            switch (data.type) {
            case 'chunk':
                if (data.text) callbacks.onChunk(data.text)
                break
            case 'script_done':
                callbacks.onScriptDone?.()
                break
            case 'synthesizing':
                callbacks.onSynthesizing?.()
                break
            case 'done':
                callbacks.onDone({
                    resourceId: data.resource_id,
                    hasAudio: data.has_audio === '1',
                    audioResourceId: data.audio_resource_id,
                    audioError: data.audio_error,
                })
                closedByBusiness = true
                ctrl.abort()
                break
            case 'error':
                callbacks.onError(data.message || '生成失败')
                closedByBusiness = true
                ctrl.abort()
                break
            }
        },
        onerror(err) {
            // 默默重连——这是断点续传的核心。返回 undefined 走默认延迟。
            // 业务关闭的不进这里（abort 直接结束）。
            console.warn('生成流连接错误，重连中:', err)
        },
        onclose() {
            // 业务关闭（done/error sentinel 已收到）：抛异常停止重连
            // 非业务关闭（nginx 切连接 / server 进程重启等）：默认行为是重连，
            // 不 throw 让 fetchEventSource 自动续上，带 Last-Event-ID 续读 stream
            if (closedByBusiness) {
                throw new Error('Stream closed by business')
            }
        },
    })

    return () => {
        closedByBusiness = true
        ctrl.abort()
    }
}
