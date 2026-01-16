import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import { createTask, getTask, getDefaultPrompts } from '@/api/task'
import type {
    PageState,
    TaskStatus,
    CurrentTab,
    ProgressInfo,
    TaskResult,
    StatusMap,
    TaskResponse,
    CustomPrompts
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

    // 提示词状态
    const promptsLoaded: Ref<boolean> = ref(false)
    const prompts: CustomPrompts = reactive({
        outlineSystem: '',
        outlineUser: '',
        articleSystem: '',
        articleUser: ''
    })

    // localStorage key
    const PROMPTS_STORAGE_KEY = 'v2t_custom_prompts'

    // 保存最后一次提交的参数，用于重试
    let lastUrl: string = ''
    let lastDownloadOnly: boolean = false
    let lastPrompts: CustomPrompts = { outlineSystem: '', outlineUser: '', articleSystem: '', articleUser: '' }
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

    // 从 localStorage 加载提示词
    const loadPromptsFromStorage = (): CustomPrompts | null => {
        try {
            const stored = localStorage.getItem(PROMPTS_STORAGE_KEY)
            if (stored) {
                return JSON.parse(stored) as CustomPrompts
            }
        } catch (error) {
            console.error('读取 localStorage 失败:', error)
        }
        return null
    }

    // 保存提示词到 localStorage
    const savePromptsToStorage = (): void => {
        try {
            localStorage.setItem(PROMPTS_STORAGE_KEY, JSON.stringify(prompts))
        } catch (error) {
            console.error('保存到 localStorage 失败:', error)
        }
    }

    // 初始化提示词：优先从 localStorage 读取，否则使用后端默认值
    const loadPrompts = async (): Promise<void> => {
        if (promptsLoaded.value) return

        // 先尝试从 localStorage 读取
        const stored = loadPromptsFromStorage()
        if (stored) {
            Object.assign(prompts, stored)
            promptsLoaded.value = true
            return
        }

        // 否则从后端获取默认值
        try {
            const defaults = await getDefaultPrompts()
            prompts.outlineSystem = defaults.outline_system
            prompts.outlineUser = defaults.outline_user
            prompts.articleSystem = defaults.article_system
            prompts.articleUser = defaults.article_user
            promptsLoaded.value = true
        } catch (error) {
            console.error('加载默认提示词失败:', error)
        }
    }

    // 重置所有提示词为默认值
    const resetPrompts = async (): Promise<void> => {
        localStorage.removeItem(PROMPTS_STORAGE_KEY)
        try {
            const defaults = await getDefaultPrompts()
            prompts.outlineSystem = defaults.outline_system
            prompts.outlineUser = defaults.outline_user
            prompts.articleSystem = defaults.article_system
            prompts.articleUser = defaults.article_user
        } catch (error) {
            console.error('重置提示词失败:', error)
        }
    }

    // 重置大纲提示词
    const resetOutlinePrompts = async (): Promise<void> => {
        try {
            const defaults = await getDefaultPrompts()
            prompts.outlineSystem = defaults.outline_system
            prompts.outlineUser = defaults.outline_user
            savePromptsToStorage()
        } catch (error) {
            console.error('重置大纲提示词失败:', error)
        }
    }

    // 重置文章提示词
    const resetArticlePrompts = async (): Promise<void> => {
        try {
            const defaults = await getDefaultPrompts()
            prompts.articleSystem = defaults.article_system
            prompts.articleUser = defaults.article_user
            savePromptsToStorage()
        } catch (error) {
            console.error('重置文章提示词失败:', error)
        }
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
        lastPrompts = { ...prompts }
        // 保存当前提示词到 localStorage
        savePromptsToStorage()
        resetState()
        page.value = 'result'

        try {
            const data = await createTask(url.value, lastDownloadOnly, lastPrompts)
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
        Object.assign(prompts, lastPrompts)
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
        promptsLoaded,
        prompts,

        // 计算属性
        currentContent,

        // 方法
        resetState,
        loadPrompts,
        savePromptsToStorage,
        resetPrompts,
        resetOutlinePrompts,
        resetArticlePrompts,
        submitUrl,
        startNew,
        retryTask,
        copyContent
    }
})

export type TaskStore = ReturnType<typeof useTaskStore>
