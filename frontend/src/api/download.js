/**
 * URL 下载 API
 */

/**
 * 创建 URL 下载任务
 * @param {string} url - 视频链接
 * @returns {Promise<{id: string, status: string, video_id: string|null, created: boolean}>}
 */
export async function createUrlDownload(url) {
    const response = await fetch('/api/url-downloads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    })
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '创建下载任务失败')
    }

    return data
}

/**
 * 获取下载状态
 * @param {string} downloadId - 下载ID
 * @returns {Promise<Object>}
 */
export async function getUrlDownload(downloadId) {
    const response = await fetch(`/api/url-downloads/${downloadId}`)
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '获取下载状态失败')
    }

    return data
}

/**
 * 订阅下载进度 (SSE)
 * @param {string} downloadId - 下载ID
 * @returns {EventSource}
 */
export function subscribeDownloadEvents(downloadId) {
    return new EventSource(`/api/url-downloads/${downloadId}/events`)
}
