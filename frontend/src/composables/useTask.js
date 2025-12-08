import { ref, reactive, computed } from 'vue'

export function useTask() {
    // 状态
    const page = ref('initial')
    const url = ref('')
    const downloadOnly = ref(false)
    const taskId = ref(null)
    const taskStatus = ref('pending')
    const currentTab = ref('article')
    const errorMessage = ref('无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。')

    const progress = reactive({
        title: '',
        text: '准备中...',
        percent: 10,
        step: '步骤 1/3'
    })

    const result = reactive({
        title: '',
        has_video: false,
        has_audio: false,
        article: '',
        outline: '',
        transcript: ''
    })

    let pollInterval = null
    let lastUrl = ''
    let lastDownloadOnly = false

    // 计算属性
    const isProcessing = computed(() => {
        return taskStatus.value !== 'completed' && taskStatus.value !== 'failed'
    })

    const isFailed = computed(() => {
        return taskStatus.value === 'failed'
    })

    // 是否有文字内容（用于判断是否显示内容区域）
    const hasTextContent = computed(() => {
        return !!(result.transcript || result.outline || result.article)
    })

    const currentContent = computed(() => {
        if (currentTab.value === 'article') return result.article || ''
        if (currentTab.value === 'outline') return result.outline || ''
        return result.transcript || ''
    })

    const isContentLoading = computed(() => {
        if (!isProcessing.value && !isFailed.value) {
            // 处理完成后，如果内容为空则显示提示
            return false
        }
        // 处理中，根据当前tab判断内容是否已加载
        if (currentTab.value === 'transcript') {
            return !result.transcript
        }
        if (currentTab.value === 'outline') {
            return !result.outline && isProcessing.value
        }
        if (currentTab.value === 'article') {
            return !result.article && isProcessing.value
        }
        return false
    })

    const contentLoadingText = computed(() => {
        if (currentTab.value === 'transcript') {
            if (taskStatus.value === 'downloading') return '正在下载视频，转录内容稍后显示...'
            if (taskStatus.value === 'transcribing') return '正在转录音频...'
            return '准备中...'
        }
        if (currentTab.value === 'outline' || currentTab.value === 'article') {
            if (taskStatus.value === 'downloading') return '正在下载视频...'
            if (taskStatus.value === 'transcribing') return '正在转录音频...'
            if (taskStatus.value === 'generating') return '正在生成内容...'
            return '准备中...'
        }
        return '加载中...'
    })

    // 方法
    const resetState = () => {
        taskId.value = null
        taskStatus.value = 'pending'
        currentTab.value = 'article'
        errorMessage.value = '无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。'
        Object.assign(progress, { title: '', text: '准备中...', percent: 10, step: '步骤 1/3' })
        Object.assign(result, { title: '', has_video: false, has_audio: false, article: '', outline: '', transcript: '' })
    }

    const startNew = () => {
        if (pollInterval) clearInterval(pollInterval)
        resetState()
        url.value = ''
        page.value = 'initial'
    }

    const retryTask = () => {
        if (pollInterval) clearInterval(pollInterval)
        resetState()
        url.value = lastUrl
        downloadOnly.value = lastDownloadOnly
        submitUrl()
    }

    const submitUrl = async () => {
        if (!url.value.trim()) {
            alert('请输入视频链接')
            return
        }

        lastUrl = url.value
        lastDownloadOnly = downloadOnly.value
        resetState()
        page.value = 'result'

        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url.value, download_only: lastDownloadOnly })
            })
            const data = await response.json()

            if (!response.ok) {
                throw new Error(data.detail || '提交失败')
            }

            taskId.value = data.task_id
            startPolling()
        } catch (error) {
            errorMessage.value = error.message
            taskStatus.value = 'failed'
        }
    }

    const startPolling = () => {
        if (pollInterval) clearInterval(pollInterval)
        pollInterval = setInterval(checkTask, 2000)
        checkTask()
    }

    const checkTask = async () => {
        if (!taskId.value) return

        try {
            const response = await fetch(`/api/task/${taskId.value}`)
            const data = await response.json()

            // 更新任务状态
            taskStatus.value = data.status

            // 渐进更新数据
            if (data.title) {
                progress.title = data.title
                result.title = data.title
            }
            if (data.has_video) result.has_video = true
            if (data.has_audio) result.has_audio = true
            if (data.transcript) result.transcript = data.transcript
            if (data.outline) result.outline = data.outline
            if (data.article) result.article = data.article

            // 更新进度条
            const statusMap = {
                'pending': { text: '等待处理...', percent: 10, step: '步骤 1/3' },
                'downloading': { text: '正在下载视频...', percent: 33, step: '步骤 1/3' },
                'transcribing': { text: '正在转录音频...', percent: 55, step: '步骤 2/3' },
                'generating': { text: '正在生成内容...', percent: 80, step: '步骤 3/3' },
                'completed': { text: '处理完成', percent: 100, step: '完成' },
            }

            if (statusMap[data.status]) {
                const s = statusMap[data.status]
                progress.text = data.progress || s.text
                progress.percent = s.percent
                progress.step = s.step
            }

            // 自动切换到有内容的tab
            if (result.transcript && !result.outline && !result.article && currentTab.value !== 'transcript') {
                currentTab.value = 'transcript'
            }

            if (data.status === 'completed') {
                clearInterval(pollInterval)
                // 切换到最佳内容tab
                currentTab.value = result.article ? 'article' : (result.outline ? 'outline' : 'transcript')
            } else if (data.status === 'failed') {
                clearInterval(pollInterval)
                errorMessage.value = data.error || '处理失败'
            }
        } catch (error) {
            console.error('轮询失败:', error)
        }
    }

    const copyContent = () => {
        if (!currentContent.value) return
        navigator.clipboard.writeText(currentContent.value).then(() => {
            alert('已复制到剪贴板')
        }).catch(() => {
            alert('复制失败，请手动选择复制')
        })
    }

    return {
        page,
        url,
        downloadOnly,
        taskId,
        taskStatus,
        currentTab,
        errorMessage,
        progress,
        result,
        isProcessing,
        isFailed,
        hasTextContent,
        currentContent,
        isContentLoading,
        contentLoadingText,
        startNew,
        retryTask,
        submitUrl,
        copyContent
    }
}
