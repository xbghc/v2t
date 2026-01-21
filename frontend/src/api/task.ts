import { fetchEventSource } from '@microsoft/fetch-event-source'
import type {
    PromptsResponse,
    VideoTaskResponse,
    OutlineTaskResponse,
    ArticleTaskResponse,
    PodcastTaskResponse,
    VideoStatusStreamData,
} from '@/types'

// 任务响应联合类型
type TaskResponse = VideoTaskResponse | OutlineTaskResponse | ArticleTaskResponse | PodcastTaskResponse

// API 基础路径，使用 Vite 的 base 配置
const API_BASE = `${import.meta.env.BASE_URL}api`

/**
 * 流式请求参数
 */
interface StreamPrompts {
    systemPrompt: string
    userPrompt: string
}

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
 * 创建视频处理任务
 */
export async function createVideoTask(url: string): Promise<VideoTaskResponse> {
    const response = await fetch(`${API_BASE}/process-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    })
    const data = await response.json() as VideoTaskResponse | { detail: string }

    if (!response.ok) {
        throw new Error((data as { detail: string }).detail || '提交失败')
    }

    return data as VideoTaskResponse
}

/**
 * 获取任务状态（通用）
 */
export async function getTask(taskId: string): Promise<TaskResponse> {
    const response = await fetch(`${API_BASE}/task/${taskId}`)
    return response.json() as Promise<TaskResponse>
}

/**
 * 获取视频任务状态
 */
export async function getVideoTask(taskId: string): Promise<VideoTaskResponse> {
    const response = await fetch(`${API_BASE}/task/${taskId}`)
    return response.json() as Promise<VideoTaskResponse>
}

/**
 * 获取大纲任务状态
 */
export async function getOutlineTask(taskId: string): Promise<OutlineTaskResponse> {
    const response = await fetch(`${API_BASE}/task/${taskId}`)
    return response.json() as Promise<OutlineTaskResponse>
}

/**
 * 获取文章任务状态
 */
export async function getArticleTask(taskId: string): Promise<ArticleTaskResponse> {
    const response = await fetch(`${API_BASE}/task/${taskId}`)
    return response.json() as Promise<ArticleTaskResponse>
}

/**
 * 获取播客任务状态
 */
export async function getPodcastTask(taskId: string): Promise<PodcastTaskResponse> {
    const response = await fetch(`${API_BASE}/task/${taskId}`)
    return response.json() as Promise<PodcastTaskResponse>
}

/**
 * SSE 流式监听视频任务状态变化
 * @returns 清理函数
 */
export function streamVideoTaskStatus(
    taskId: string,
    onStatusChange: (data: VideoStatusStreamData) => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`${API_BASE}/task/${taskId}/status-stream`, {
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
            const data = JSON.parse(ev.data) as VideoStatusStreamData
            onStatusChange(data)
            // 终态自动关闭连接
            if (data.status === 'completed' || data.status === 'failed' || data.status === 'ready') {
                ctrl.abort()
            }
        },
        onerror(err) {
            onError(err instanceof Error ? err.message : '连接错误')
            throw err
        },
        onclose() {
            // SSE 连接正常关闭（到达终态后）
        },
    })

    return () => ctrl.abort()
}

/**
 * 文本转播客任务
 */
export async function createPodcastTask(
    text: string,
    title: string = '',
    podcastSystemPrompt: string = '',
    podcastUserPrompt: string = ''
): Promise<PodcastTaskResponse> {
    const response = await fetch(`${API_BASE}/text-to-podcast`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text,
            title,
            podcast_system_prompt: podcastSystemPrompt,
            podcast_user_prompt: podcastUserPrompt,
        })
    })
    const data = await response.json() as PodcastTaskResponse | { detail: string }

    if (!response.ok) {
        throw new Error((data as { detail: string }).detail || '提交失败')
    }

    return data as PodcastTaskResponse
}

/**
 * 流式生成大纲
 * @param videoTaskId 视频任务 ID（用于获取转录内容）
 * @param onTaskCreated 新建的大纲任务 ID 回调
 * @returns 清理函数
 */
export function streamOutline(
    videoTaskId: string,
    prompts: StreamPrompts,
    onTaskCreated: (taskId: string) => void,
    onChunk: (content: string) => void,
    onDone: () => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`${API_BASE}/task/${videoTaskId}/stream/outline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            system_prompt: prompts.systemPrompt,
            user_prompt: prompts.userPrompt
        }),
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
            const data = JSON.parse(ev.data) as { task_id?: string; content?: string; done?: boolean; error?: string }
            if (data.error) {
                onError(data.error)
                ctrl.abort()
            } else if (data.task_id) {
                onTaskCreated(data.task_id)
            } else if (data.done) {
                onDone()
                ctrl.abort()
            } else if (data.content) {
                onChunk(data.content)
            }
        },
        onerror(err) {
            onError(err instanceof Error ? err.message : '连接错误')
            throw err
        },
        onclose() {
            throw new Error('Stream closed')
        },
    })

    return () => ctrl.abort()
}

/**
 * 流式生成文章
 * @param videoTaskId 视频任务 ID（用于获取转录内容）
 * @param onTaskCreated 新建的文章任务 ID 回调
 * @returns 清理函数
 */
export function streamArticle(
    videoTaskId: string,
    prompts: StreamPrompts,
    onTaskCreated: (taskId: string) => void,
    onChunk: (content: string) => void,
    onDone: () => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`${API_BASE}/task/${videoTaskId}/stream/article`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            system_prompt: prompts.systemPrompt,
            user_prompt: prompts.userPrompt
        }),
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
            const data = JSON.parse(ev.data) as { task_id?: string; content?: string; done?: boolean; error?: string }
            if (data.error) {
                onError(data.error)
                ctrl.abort()
            } else if (data.task_id) {
                onTaskCreated(data.task_id)
            } else if (data.done) {
                onDone()
                ctrl.abort()
            } else if (data.content) {
                onChunk(data.content)
            }
        },
        onerror(err) {
            onError(err instanceof Error ? err.message : '连接错误')
            throw err
        },
        onclose() {
            throw new Error('Stream closed')
        },
    })

    return () => ctrl.abort()
}

/**
 * 播客流式事件数据
 */
interface PodcastStreamData {
    task_id?: string
    content?: string
    script_done?: boolean
    synthesizing?: boolean
    done?: boolean
    has_audio?: boolean
    audio_error?: string
    error?: string
}

/**
 * 流式生成播客（脚本 + 音频合成）
 * @param videoTaskId 视频任务 ID（用于获取转录内容）
 * @param onTaskCreated 新建的播客任务 ID 回调
 * @returns 清理函数
 */
export function streamPodcast(
    videoTaskId: string,
    prompts: StreamPrompts,
    onTaskCreated: (taskId: string) => void,
    onScriptChunk: (content: string) => void,
    onScriptDone: () => void,
    onSynthesizing: () => void,
    onDone: (hasAudio: boolean, audioError?: string) => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`${API_BASE}/task/${videoTaskId}/stream/podcast`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            system_prompt: prompts.systemPrompt,
            user_prompt: prompts.userPrompt
        }),
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
            const data = JSON.parse(ev.data) as PodcastStreamData
            if (data.error) {
                onError(data.error)
                ctrl.abort()
            } else if (data.task_id) {
                onTaskCreated(data.task_id)
            } else if (data.done) {
                onDone(data.has_audio || false, data.audio_error)
                ctrl.abort()
            } else if (data.synthesizing) {
                onSynthesizing()
            } else if (data.script_done) {
                onScriptDone()
            } else if (data.content) {
                onScriptChunk(data.content)
            }
        },
        onerror(err) {
            onError(err instanceof Error ? err.message : '连接错误')
            throw err
        },
        onclose() {
            throw new Error('Stream closed')
        },
    })

    return () => ctrl.abort()
}
