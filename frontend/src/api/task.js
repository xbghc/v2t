/**
 * 创建视频处理任务
 * @param {string} url - 视频链接
 * @param {boolean} downloadOnly - 是否仅下载
 * @returns {Promise<{task_id: string}>}
 */
export async function createTask(url, downloadOnly = false) {
    const response = await fetch('api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, download_only: downloadOnly })
    })
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '提交失败')
    }

    return data
}

/**
 * 获取任务状态
 * @param {string} taskId - 任务ID
 * @returns {Promise<Object>}
 */
export async function getTask(taskId) {
    const response = await fetch(`api/task/${taskId}`)
    return response.json()
}
