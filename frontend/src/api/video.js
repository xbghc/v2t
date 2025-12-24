/**
 * 视频 API
 */

/**
 * 创建视频（开始下载）
 * @param {string} url - 视频链接
 * @returns {Promise<{id: string, status: string, created: boolean}>}
 */
export async function createVideo(url) {
    const response = await fetch('/api/videos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    })
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '创建失败')
    }

    return data
}

/**
 * 获取视频状态
 * @param {string} videoId - 视频ID
 * @returns {Promise<Object>}
 */
export async function getVideo(videoId) {
    const response = await fetch(`/api/videos/${videoId}`)
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '获取失败')
    }

    return data
}

/**
 * 删除视频
 * @param {string} videoId - 视频ID
 */
export async function deleteVideo(videoId) {
    const response = await fetch(`/api/videos/${videoId}`, {
        method: 'DELETE'
    })

    if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || '删除失败')
    }
}

/**
 * 订阅视频下载进度 (SSE)
 * @param {string} videoId - 视频ID
 * @returns {EventSource}
 */
export function subscribeVideoEvents(videoId) {
    return new EventSource(`/api/videos/${videoId}/events`)
}
