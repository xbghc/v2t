/**
 * 视频 API
 */

/**
 * 上传视频文件
 * @param {File} file - 视频文件
 * @returns {Promise<{id: string, title: string}>}
 */
export async function uploadVideo(file) {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch('/api/videos/upload', {
        method: 'POST',
        body: formData
    })
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '上传视频失败')
    }

    return data
}

/**
 * 获取视频信息
 * @param {string} videoId - 视频ID
 * @returns {Promise<Object>}
 */
export async function getVideo(videoId) {
    const response = await fetch(`/api/videos/${videoId}`)
    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || '获取视频失败')
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
        throw new Error(data.detail || '删除视频失败')
    }
}
