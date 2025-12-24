/**
 * 转录 API
 */

/**
 * 创建转录
 * @param {string} videoId - 视频ID
 * @returns {Promise<{id: string, status: string}>}
 */
export async function createTranscript(videoId) {
    const response = await fetch('/api/transcripts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_id: videoId })
    })
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '创建转录失败')
    }

    return data
}

/**
 * 获取转录状态
 * @param {string} transcriptId - 转录ID
 * @returns {Promise<Object>}
 */
export async function getTranscript(transcriptId) {
    const response = await fetch(`/api/transcripts/${transcriptId}`)
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '获取失败')
    }

    return data
}

/**
 * 订阅转录进度 (SSE)
 * @param {string} transcriptId - 转录ID
 * @returns {EventSource}
 */
export function subscribeTranscriptEvents(transcriptId) {
    return new EventSource(`/api/transcripts/${transcriptId}/events`)
}

/**
 * 创建大纲
 * @param {string} transcriptId - 转录ID
 * @returns {Promise<{id: string, status: string}>}
 */
export async function createOutline(transcriptId) {
    const response = await fetch(`/api/transcripts/${transcriptId}/outline`, {
        method: 'POST'
    })
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '创建大纲失败')
    }

    return data
}

/**
 * 获取大纲
 * @param {string} transcriptId - 转录ID
 * @returns {Promise<Object>}
 */
export async function getOutline(transcriptId) {
    const response = await fetch(`/api/transcripts/${transcriptId}/outline`)
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '获取大纲失败')
    }

    return data
}

/**
 * 订阅大纲生成进度 (SSE)
 * @param {string} transcriptId - 转录ID
 * @returns {EventSource}
 */
export function subscribeOutlineEvents(transcriptId) {
    return new EventSource(`/api/transcripts/${transcriptId}/outline/events`)
}

/**
 * 创建文章
 * @param {string} transcriptId - 转录ID
 * @returns {Promise<{id: string, status: string}>}
 */
export async function createArticle(transcriptId) {
    const response = await fetch(`/api/transcripts/${transcriptId}/article`, {
        method: 'POST'
    })
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '创建文章失败')
    }

    return data
}

/**
 * 获取文章
 * @param {string} transcriptId - 转录ID
 * @returns {Promise<Object>}
 */
export async function getArticle(transcriptId) {
    const response = await fetch(`/api/transcripts/${transcriptId}/article`)
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '获取文章失败')
    }

    return data
}

/**
 * 订阅文章生成进度 (SSE)
 * @param {string} transcriptId - 转录ID
 * @returns {EventSource}
 */
export function subscribeArticleEvents(transcriptId) {
    return new EventSource(`/api/transcripts/${transcriptId}/article/events`)
}
