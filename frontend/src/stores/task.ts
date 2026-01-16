import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import { createTask, getTask } from '@/api/task'
import type {
    PageState,
    TaskStatus,
    CurrentTab,
    ProgressInfo,
    TaskResult,
    StatusMap,
    TaskResponse
} from '@/types'

export const useTaskStore = defineStore('task', () => {
    // 页面状态
    const page: Ref<PageState> = ref('initial')

    // 表单输入
    const url: Ref<string> = ref('')
    const downloadOnly: Ref<boolean> = ref(false)

    // 任务状态
    const taskId: Ref<string | null> = ref(null)
    const taskStatus: Ref<TaskStatus> = ref('pending')
    const currentTab: Ref<CurrentTab> = ref('article')
    const errorMessage: Ref<string> = ref('无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。')

    // 进度信息
    const progress: ProgressInfo = reactive({
        title: '',
        text: '准备中...',
        percent: 10,
        step: '步骤 1/3'
    })

    // 处理结果
    const result: TaskResult = reactive({
        title: '',
        has_video: false,
        has_audio: false,
        article: '',
        outline: '',
        transcript: ''
    })

    // 保存最后一次提交的参数，用于重试
    let lastUrl: string = ''
    let lastDownloadOnly: boolean = false
    let pollTimer: ReturnType<typeof setInterval> | null = null

    // 状态映射
    const statusMap: StatusMap = {
        'pending': { text: '等待处理...', percent: 10, step: '步骤 1/3' },
        'downloading': { text: '正在下载视频...', percent: 33, step: '步骤 1/3' },
        'transcribing': { text: '正在转录音频...', percent: 55, step: '步骤 2/3' },
        'generating': { text: '正在生成内容...', percent: 80, step: '步骤 3/3' },
        'completed': { text: '处理完成', percent: 100, step: '完成' }
    }

    // 计算属性：当前内容（用于复制）
    const currentContent: ComputedRef<string> = computed(() => {
        if (currentTab.value === 'article') return result.article || ''
        if (currentTab.value === 'outline') return result.outline || ''
        return result.transcript || ''
    })

    // 重置状态
    const resetState = (): void => {
        taskStatus.value = 'pending'
        currentTab.value = 'article'
        errorMessage.value = '无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。'
        Object.assign(progress, { title: '', text: '准备中...', percent: 10, step: '步骤 1/3' })
        Object.assign(result, { title: '', has_video: false, has_audio: false, article: '', outline: '', transcript: '' })
    }

    // 停止轮询
    const stopPolling = (): void => {
        if (pollTimer) {
            clearInterval(pollTimer)
            pollTimer = null
        }
    }

    // 轮询任务状态
    const poll = async (): Promise<void> => {
        if (!taskId.value) return

        try {
            const data = await getTask(taskId.value)
            handleTaskUpdate(data)

            if (data.status === 'completed') {
                stopPolling()
                handleTaskComplete()
            } else if (data.status === 'failed') {
                stopPolling()
                handleTaskFailed(data)
            }
        } catch (error) {
            console.error('轮询失败:', error)
        }
    }

    // 开始轮询
    const startPolling = (id: string): void => {
        taskId.value = id
        stopPolling()
        pollTimer = setInterval(poll, 2000)
        poll()
    }

    // 处理任务更新
    const handleTaskUpdate = (data: TaskResponse): void => {
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
        const statusInfo = statusMap[data.status]
        if (statusInfo) {
            progress.text = data.progress || statusInfo.text
            progress.percent = statusInfo.percent
            progress.step = statusInfo.step
        }

        // 自动切换到有内容的 tab
        if (result.transcript && !result.outline && !result.article && currentTab.value !== 'transcript') {
            currentTab.value = 'transcript'
        }
    }

    // 处理任务完成
    const handleTaskComplete = (): void => {
        currentTab.value = result.article ? 'article' : (result.outline ? 'outline' : 'transcript')
    }

    // 处理任务失败
    const handleTaskFailed = (data: TaskResponse): void => {
        errorMessage.value = data.error || '处理失败'
    }

    // 提交 URL
    const submitUrl = async (): Promise<void> => {
        if (!url.value.trim()) {
            alert('请输入视频链接')
            return
        }

        lastUrl = url.value
        lastDownloadOnly = downloadOnly.value
        resetState()
        page.value = 'result'

        try {
            const data = await createTask(url.value, lastDownloadOnly)
            startPolling(data.task_id)
        } catch (error) {
            errorMessage.value = (error as Error).message
            taskStatus.value = 'failed'
        }
    }

    // 开始新任务
    const startNew = (): void => {
        stopPolling()
        resetState()
        url.value = ''
        page.value = 'initial'
    }

    // 重试任务
    const retryTask = (): void => {
        stopPolling()
        resetState()
        url.value = lastUrl
        downloadOnly.value = lastDownloadOnly
        submitUrl()
    }

    // 复制当前内容
    const copyContent = (): void => {
        if (!currentContent.value) return
        navigator.clipboard.writeText(currentContent.value).then(() => {
            alert('已复制到剪贴板')
        }).catch(() => {
            alert('复制失败，请手动选择复制')
        })
    }

    return {
        // 状态
        page,
        url,
        downloadOnly,
        taskId,
        taskStatus,
        currentTab,
        errorMessage,
        progress,
        result,

        // 计算属性
        currentContent,

        // 方法
        resetState,
        submitUrl,
        startNew,
        retryTask,
        copyContent
    }
})

export type TaskStore = ReturnType<typeof useTaskStore>
