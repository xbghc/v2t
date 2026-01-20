import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { CreateTaskResponse, CustomPrompts, GenerateOptions, PromptsResponse, TaskResponse } from '@/types'

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
 * 流式生成大纲
 * @returns 清理函数
 */
export function streamOutline(
    taskId: string,
    onChunk: (content: string) => void,
    onDone: () => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`api/task/${taskId}/stream/outline`, {
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
            const data = JSON.parse(ev.data) as { content?: string; done?: boolean; error?: string }
            if (data.error) {
                onError(data.error)
                ctrl.abort()
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
    taskId: string,
    onChunk: (content: string) => void,
    onDone: () => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`api/task/${taskId}/stream/article`, {
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
            const data = JSON.parse(ev.data) as { content?: string; done?: boolean; error?: string }
            if (data.error) {
                onError(data.error)
                ctrl.abort()
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
 * @returns 清理函数
 */
export function streamPodcast(
    taskId: string,
    onScriptChunk: (content: string) => void,
    onScriptDone: () => void,
    onSynthesizing: () => void,
    onDone: (hasAudio: boolean, audioError?: string) => void,
    onError: (error: string) => void
): () => void {
    const ctrl = new AbortController()

    fetchEventSource(`api/task/${taskId}/stream/podcast`, {
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
