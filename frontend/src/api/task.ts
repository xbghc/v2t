import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { CreateTaskResponse, CustomPrompts, GenerateOptions, PromptsResponse, StreamEventData, TaskResponse } from '@/types'

/**
 * 获取默认提示词
 */
export async function getDefaultPrompts(): Promise<PromptsResponse> {
    const response = await fetch('api/prompts')
    if (!response.ok) {
        throw new Error('获取默认提示词失败')
    }
    return response.json() as Promise<PromptsResponse>
}

/**
 * 创建视频处理任务
 */
export async function createTask(
    url: string,
    generateOptions: GenerateOptions,
    prompts?: CustomPrompts
): Promise<CreateTaskResponse> {
    const response = await fetch('api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            url,
            generate_outline: generateOptions.outline,
            generate_article: generateOptions.article,
            generate_podcast: generateOptions.podcast,
            outline_system_prompt: prompts?.outlineSystem || '',
            outline_user_prompt: prompts?.outlineUser || '',
            article_system_prompt: prompts?.articleSystem || '',
            article_user_prompt: prompts?.articleUser || '',
            podcast_system_prompt: prompts?.podcastSystem || '',
            podcast_user_prompt: prompts?.podcastUser || '',
        })
    })
    const data = await response.json() as CreateTaskResponse | { detail: string }

    if (!response.ok) {
        throw new Error((data as { detail: string }).detail || '提交失败')
    }

    return data as CreateTaskResponse
}

/**
 * 获取任务状态
 */
export async function getTask(taskId: string): Promise<TaskResponse> {
    const response = await fetch(`api/task/${taskId}`)
    return response.json() as Promise<TaskResponse>
}

/**
 * 文本转播客任务
 */
export async function textToPodcast(
    text: string,
    title: string = '',
    podcastSystemPrompt: string = '',
    podcastUserPrompt: string = ''
): Promise<CreateTaskResponse> {
    const response = await fetch('api/text-to-podcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text,
            title,
            podcast_system_prompt: podcastSystemPrompt,
            podcast_user_prompt: podcastUserPrompt,
        })
    })
    const data = await response.json() as CreateTaskResponse | { detail: string }

    if (!response.ok) {
        throw new Error((data as { detail: string }).detail || '提交失败')
    }

    return data as CreateTaskResponse
}

/**
 * 流式事件回调接口
 */
export interface StreamCallbacks {
    onOutline?: (content: string, done: boolean) => void
    onArticle?: (content: string, done: boolean) => void
    onPodcastStart?: () => void
    onPodcastDone?: (script: string, hasAudio: boolean, error: string) => void
    onComplete?: () => void
    onError?: (type: string, message: string) => void
}

/**
 * 连接 SSE 流式端点获取生成内容
 * @returns 清理函数，调用后关闭连接
 */
export function streamTaskContent(
    taskId: string,
    callbacks: StreamCallbacks
): () => void {
    const ctrl = new AbortController()
    let completed = false

    fetchEventSource(`api/task/${taskId}/stream`, {
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
            const eventType = ev.event
            const data = ev.data ? JSON.parse(ev.data) as StreamEventData : {}

            switch (eventType) {
            case 'outline':
                callbacks.onOutline?.(data.content || '', data.done || false)
                break
            case 'article':
                callbacks.onArticle?.(data.content || '', data.done || false)
                break
            case 'podcast_start':
                callbacks.onPodcastStart?.()
                break
            case 'podcast_done':
                callbacks.onPodcastDone?.(data.script || '', data.has_audio || false, data.error || '')
                break
            case 'complete':
                completed = true
                callbacks.onComplete?.()
                ctrl.abort()
                break
            case 'error':
                completed = true
                callbacks.onError?.(data.type || 'unknown', data.message || '未知错误')
                ctrl.abort()
                break
            }
        },
        onerror(err) {
            if (!completed) {
                callbacks.onError?.('connection', err instanceof Error ? err.message : '连接错误')
            }
            throw err
        },
        onclose() {
            // 阻止自动重连
            throw new Error('Stream closed')
        },
    })

    return () => ctrl.abort()
}
