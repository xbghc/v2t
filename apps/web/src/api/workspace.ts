import { fetchEventSource } from '@microsoft/fetch-event-source'
import type {
    PromptsResponse,
    WorkspaceResponse,
    StreamPrompts,
} from '@/types'

// API 基础路径，使用 Vite 的 base 配置
const API_BASE = `${import.meta.env.BASE_URL}api`

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
export async function createWorkspace(url: string): Promise<WorkspaceResponse> {
    const response = await fetch(`${API_BASE}/workspaces`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    })
    const data = await response.json() as WorkspaceResponse | { detail: string }

    if (!response.ok) {
        throw new Error((data as { detail: string }).detail || '创建工作区失败')
    }

    return data as WorkspaceResponse
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
 * @returns 清理函数
 */
export function streamWorkspaceStatus(
    workspaceId: string,
    onStatusChange: (data: WorkspaceResponse) => void,
    onError: (error: string) => void
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
            const data = JSON.parse(ev.data) as WorkspaceResponse
            onStatusChange(data)
            // 终态自动关闭连接
            if (data.status === 'failed' || data.status === 'ready') {
                ctrl.abort()
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
 * 流式生成事件数据
 */
interface StreamEventData {
    resource_id?: string
    content?: string
    done?: boolean
    error?: string
    // 播客特有
    script_done?: boolean
    synthesizing?: boolean
    has_audio?: boolean
    audio_error?: string
    audio_resource_id?: string
}

/**
 * 流式生成大纲
 * @returns 清理函数
 */
export function streamOutline(
    workspaceId: string,
    prompts: StreamPrompts,
    onResourceCreated: (resourceId: string) => void,
    onChunk: (content: string) => void,
    onDone: () => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`${API_BASE}/workspaces/${workspaceId}/stream/outline`, {
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
            const data = JSON.parse(ev.data) as StreamEventData
            if (data.error) {
                onError(data.error)
                ctrl.abort()
            } else if (data.resource_id) {
                onResourceCreated(data.resource_id)
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
 * @returns 清理函数
 */
export function streamArticle(
    workspaceId: string,
    prompts: StreamPrompts,
    onResourceCreated: (resourceId: string) => void,
    onChunk: (content: string) => void,
    onDone: () => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`${API_BASE}/workspaces/${workspaceId}/stream/article`, {
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
            const data = JSON.parse(ev.data) as StreamEventData
            if (data.error) {
                onError(data.error)
                ctrl.abort()
            } else if (data.resource_id) {
                onResourceCreated(data.resource_id)
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
 * 流式生成播客（脚本 + 音频合成）
 * @returns 清理函数
 */
export function streamPodcast(
    workspaceId: string,
    prompts: StreamPrompts,
    onResourceCreated: (resourceId: string) => void,
    onScriptChunk: (content: string) => void,
    onScriptDone: () => void,
    onSynthesizing: () => void,
    onDone: (hasAudio: boolean, audioResourceId?: string, audioError?: string) => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`${API_BASE}/workspaces/${workspaceId}/stream/podcast`, {
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
            const data = JSON.parse(ev.data) as StreamEventData
            if (data.error) {
                onError(data.error)
                ctrl.abort()
            } else if (data.resource_id) {
                onResourceCreated(data.resource_id)
            } else if (data.done) {
                onDone(data.has_audio || false, data.audio_resource_id, data.audio_error)
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

/**
 * 流式生成知乎文章
 * @returns 清理函数
 */
export function streamZhihuArticle(
    workspaceId: string,
    prompts: StreamPrompts,
    onResourceCreated: (resourceId: string) => void,
    onChunk: (content: string) => void,
    onDone: () => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`${API_BASE}/workspaces/${workspaceId}/stream/zhihu-article`, {
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
            const data = JSON.parse(ev.data) as StreamEventData
            if (data.error) {
                onError(data.error)
                ctrl.abort()
            } else if (data.resource_id) {
                onResourceCreated(data.resource_id)
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
