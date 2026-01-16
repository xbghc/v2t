import type { CreateTaskResponse, TaskResponse } from '@/types'

/**
 * 创建视频处理任务
 */
export async function createTask(url: string, downloadOnly: boolean = false): Promise<CreateTaskResponse> {
    const response = await fetch('api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, download_only: downloadOnly })
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
