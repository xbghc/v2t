/**
 * 音频 API
 */

/**
 * 从视频提取音频
 * @param {string} videoId - 视频ID
 * @returns {Promise<{id: string, video_id: string, title: string}>}
 */
export async function createAudio(videoId) {
    const response = await fetch('/api/audios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_id: videoId })
    })
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '创建音频失败')
    }

    return data
}

/**
 * 上传音频文件
 * @param {File} file - 音频文件
 * @returns {Promise<{id: string, title: string}>}
 */
export async function uploadAudio(file) {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch('/api/audios/upload', {
        method: 'POST',
        body: formData
    })
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '上传音频失败')
    }

    return data
}

/**
 * 获取音频状态
 * @param {string} audioId - 音频ID
 * @returns {Promise<Object>}
 */
export async function getAudio(audioId) {
    const response = await fetch(`/api/audios/${audioId}`)
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '获取音频失败')
    }

    return data
}

/**
 * 删除音频
 * @param {string} audioId - 音频ID
 */
export async function deleteAudio(audioId) {
    const response = await fetch(`/api/audios/${audioId}`, {
        method: 'DELETE'
    })

    if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || '删除音频失败')
    }
}

/**
 * 订阅音频提取进度 (SSE)
 * @param {string} audioId - 音频ID
 * @returns {EventSource}
 */
export function subscribeAudioEvents(audioId) {
    return new EventSource(`/api/audios/${audioId}/events`)
}
