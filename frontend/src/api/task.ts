import type { CreateTaskResponse, CustomPrompts, PromptsResponse, TaskResponse } from '@/types'

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
    downloadOnly: boolean = false,
    prompts?: CustomPrompts
): Promise<CreateTaskResponse> {
    const response = await fetch('api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            url,
            download_only: downloadOnly,
            outline_system_prompt: prompts?.outlineSystem || '',
            outline_user_prompt: prompts?.outlineUser || '',
            article_system_prompt: prompts?.articleSystem || '',
            article_user_prompt: prompts?.articleUser || '',
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
