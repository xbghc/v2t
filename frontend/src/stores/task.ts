import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import { createTask, getTask, getDefaultPrompts, textToPodcast, streamTaskContent } from '@/api/task'
import type {
    TaskStatus,
    CurrentTab,
    ProgressInfo,
    TaskResult,
    StatusMap,
    TaskResponse,
    CustomPrompts,
    GenerateOptions,
    InputMode
} from '@/types'

export const useTaskStore = defineStore('task', () => {
    // 输入模式
    const inputMode: Ref<InputMode> = ref('url')

    // 表单输入
    const url: Ref<string> = ref('')

    // 字幕上传状态
    const subtitleText: Ref<string> = ref('')
    const subtitleTitle: Ref<string> = ref('')

    // 生成选项（替代 downloadOnly）
    const generateOptions: GenerateOptions = reactive({
        outline: true,
        article: true,
        podcast: false
    })

    // 计算属性：是否仅下载（所有选项都未勾选）
    const isDownloadOnly: ComputedRef<boolean> = computed(() =>
        !generateOptions.outline && !generateOptions.article && !generateOptions.podcast
    )

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
        transcript: '',
        podcast_script: '',
        has_podcast_audio: false,
        podcast_error: ''
    })

    // 提示词状态
    const promptsLoaded: Ref<boolean> = ref(false)
    const prompts: CustomPrompts = reactive({
        outlineSystem: '',
        outlineUser: '',
        articleSystem: '',
        articleUser: '',
        podcastSystem: '',
        podcastUser: ''
    })

    // localStorage key
    const PROMPTS_STORAGE_KEY = 'v2t_custom_prompts'

    // 保存最后一次提交的参数，用于重试
    let lastUrl: string = ''
    let lastGenerateOptions: GenerateOptions = { outline: true, article: true, podcast: false }
    let lastPrompts: CustomPrompts = { outlineSystem: '', outlineUser: '', articleSystem: '', articleUser: '', podcastSystem: '', podcastUser: '' }
    let pollTimer: ReturnType<typeof setInterval> | null = null

    // 流式状态
    const isStreaming: Ref<boolean> = ref(false)
    const streamingOutline: Ref<string> = ref('')
    const streamingArticle: Ref<string> = ref('')
    let streamCleanup: (() => void) | null = null

    // 动态计算总步骤数
    const getTotalSteps = (): number => {
        // 基础步骤：下载 + 转录
        let steps = 2
        // 生成内容（大纲/文章）
        if (generateOptions.outline || generateOptions.article) steps++
        // 播客生成
        if (generateOptions.podcast) steps += 2  // 脚本 + 合成
        return steps
    }

    // 状态映射（根据生成选项动态调整）
    const getStatusMap = (): StatusMap => {
        const total = getTotalSteps()
        const hasPodcast = generateOptions.podcast
        const hasGenerate = generateOptions.outline || generateOptions.article

        return {
            'pending': { text: '等待处理...', percent: 5, step: `步骤 1/${total}` },
            'downloading': { text: '正在下载视频...', percent: 20, step: `步骤 1/${total}` },
            'transcribing': { text: '正在转录音频...', percent: 40, step: `步骤 2/${total}` },
            'ready_to_stream': { text: '准备生成内容...', percent: 50, step: `步骤 3/${total}` },
            'generating': { text: '正在生成内容...', percent: hasGenerate ? 60 : 40, step: `步骤 3/${total}` },
            'generating_podcast': { text: '正在生成播客脚本...', percent: hasPodcast ? 75 : 60, step: `步骤 ${hasGenerate ? 4 : 3}/${total}` },
            'synthesizing': { text: '正在合成播客音频...', percent: 90, step: `步骤 ${hasGenerate ? 5 : 4}/${total}` },
            'completed': { text: '处理完成', percent: 100, step: '完成' }
        }
    }


    // 计算属性：当前内容（用于复制）
    const currentContent: ComputedRef<string> = computed(() => {
        if (currentTab.value === 'article') return result.article || streamingArticle.value || ''
        if (currentTab.value === 'outline') return result.outline || streamingOutline.value || ''
        if (currentTab.value === 'podcast') return result.podcast_script || ''
        return result.transcript || ''
    })

    // 计算属性：显示内容（优先使用流式内容）
    const displayOutline: ComputedRef<string> = computed(() =>
        isStreaming.value ? streamingOutline.value : result.outline
    )
    const displayArticle: ComputedRef<string> = computed(() =>
        isStreaming.value ? streamingArticle.value : result.article
    )

    // 重置状态
    const resetState = (): void => {
        taskId.value = null
        taskStatus.value = 'pending'
        currentTab.value = 'article'
        errorMessage.value = '无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。'
        Object.assign(progress, { title: '', text: '准备中...', percent: 10, step: '步骤 1/3' })
        Object.assign(result, { title: '', has_video: false, has_audio: false, article: '', outline: '', transcript: '', podcast_script: '', has_podcast_audio: false })
        // 重置流式状态
        isStreaming.value = false
        streamingOutline.value = ''
        streamingArticle.value = ''
    }

    // 重置字幕状态
    const resetSubtitleState = (): void => {
        subtitleText.value = ''
        subtitleTitle.value = ''
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
            prompts.podcastSystem = defaults.podcast_system
            prompts.podcastUser = defaults.podcast_user
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
            prompts.podcastSystem = defaults.podcast_system
            prompts.podcastUser = defaults.podcast_user
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

    // 重置播客提示词
    const resetPodcastPrompts = async (): Promise<void> => {
        try {
            const defaults = await getDefaultPrompts()
            prompts.podcastSystem = defaults.podcast_system
            prompts.podcastUser = defaults.podcast_user
            savePromptsToStorage()
        } catch (error) {
            console.error('重置播客提示词失败:', error)
        }
    }

    // 停止轮询
    const stopPolling = (): void => {
        if (pollTimer) {
            clearInterval(pollTimer)
            pollTimer = null
        }
    }

    // 停止流式连接
    const stopStreaming = (): void => {
        if (streamCleanup) {
            streamCleanup()
            streamCleanup = null
        }
        isStreaming.value = false
    }

    // 启动流式连接
    const startStreaming = (id: string): void => {
        stopStreaming()
        isStreaming.value = true
        streamingOutline.value = ''
        streamingArticle.value = ''

        streamCleanup = streamTaskContent(id, {
            onOutline: (content: string, done: boolean) => {
                if (!done) {
                    streamingOutline.value += content
                } else {
                    // 流式完成，保存到结果
                    if (streamingOutline.value) {
                        result.outline = streamingOutline.value
                    }
                }
            },
            onArticle: (content: string, done: boolean) => {
                if (!done) {
                    streamingArticle.value += content
                } else {
                    // 流式完成，保存到结果
                    if (streamingArticle.value) {
                        result.article = streamingArticle.value
                    }
                }
            },
            onPodcastStart: () => {
                taskStatus.value = 'generating_podcast'
                progress.text = '正在生成播客脚本...'
            },
            onPodcastDone: (script: string, hasAudio: boolean, error: string) => {
                if (script) result.podcast_script = script
                result.has_podcast_audio = hasAudio
                if (error) result.podcast_error = error
            },
            onComplete: () => {
                isStreaming.value = false
                taskStatus.value = 'completed'
                progress.text = '处理完成'
                progress.percent = 100
                progress.step = '完成'
                handleTaskComplete()
            },
            onError: (type: string, message: string) => {
                console.error(`流式错误 [${type}]: ${message}`)
                if (type === 'fatal' || type === 'connection') {
                    isStreaming.value = false
                    taskStatus.value = 'failed'
                    errorMessage.value = message
                }
            }
        })
    }

    // 轮询任务状态
    const poll = async (): Promise<void> => {
        if (!taskId.value) return

        try {
            const data = await getTask(taskId.value)
            handleTaskUpdate(data)

            if (data.status === 'ready_to_stream') {
                // 检测到准备流式状态，停止轮询，启动流式连接
                stopPolling()
                startStreaming(taskId.value)
            } else if (data.status === 'completed') {
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
        if (data.podcast_script) result.podcast_script = data.podcast_script
        if (data.has_podcast_audio) result.has_podcast_audio = true
        if (data.podcast_error) result.podcast_error = data.podcast_error

        // 更新进度条（使用动态状态映射）
        const dynamicStatusMap = getStatusMap()
        const statusInfo = dynamicStatusMap[data.status]
        if (statusInfo) {
            progress.text = data.progress || statusInfo.text
            progress.percent = statusInfo.percent
            progress.step = statusInfo.step
        }

        // 自动切换到有内容的 tab
        if (result.transcript && !result.outline && !result.article && !result.podcast_script && currentTab.value !== 'transcript') {
            currentTab.value = 'transcript'
        }
    }

    // 处理任务完成
    const handleTaskComplete = (): void => {
        // 优先显示有内容的 tab
        if (result.article) {
            currentTab.value = 'article'
        } else if (result.outline) {
            currentTab.value = 'outline'
        } else if (result.podcast_script) {
            currentTab.value = 'podcast'
        } else {
            currentTab.value = 'transcript'
        }
    }

    // 处理任务失败
    const handleTaskFailed = (data: TaskResponse): void => {
        errorMessage.value = data.error || '处理失败'
    }

    // 提交 URL，返回 task_id 或 null（失败时）
    const submitUrl = async (): Promise<string | null> => {
        if (!url.value.trim()) {
            alert('请输入视频链接')
            return null
        }

        lastUrl = url.value
        lastGenerateOptions = { ...generateOptions }
        lastPrompts = { ...prompts }
        // 保存当前提示词到 localStorage
        savePromptsToStorage()
        resetState()

        try {
            const data = await createTask(url.value, lastGenerateOptions, lastPrompts)
            startPolling(data.task_id)
            return data.task_id
        } catch (error) {
            errorMessage.value = (error as Error).message
            taskStatus.value = 'failed'
            return null
        }
    }

    // 提交字幕转播客，返回 task_id 或 null（失败时）
    const submitSubtitle = async (): Promise<string | null> => {
        if (!subtitleText.value.trim() || subtitleText.value.length < 10) {
            alert('请上传字幕文件')
            return null
        }

        lastPrompts = { ...prompts }
        // 保存当前提示词到 localStorage
        savePromptsToStorage()
        resetState()
        // 设置字幕模式的错误信息
        errorMessage.value = '生成播客失败，请检查字幕内容是否正确，或尝试其他内容。'
        // 切换到播客 tab
        currentTab.value = 'podcast'

        try {
            const data = await textToPodcast(
                subtitleText.value,
                subtitleTitle.value,
                prompts.podcastSystem,
                prompts.podcastUser
            )
            startPolling(data.task_id)
            return data.task_id
        } catch (error) {
            errorMessage.value = (error as Error).message
            taskStatus.value = 'failed'
            return null
        }
    }

    // 开始新任务（重置状态，不处理路由）
    const startNew = (): void => {
        stopPolling()
        stopStreaming()
        resetState()
        resetSubtitleState()
        url.value = ''
    }

    // 重试任务，返回 task_id 或 null
    const retryTask = async (): Promise<string | null> => {
        stopPolling()
        stopStreaming()
        resetState()
        url.value = lastUrl
        Object.assign(generateOptions, lastGenerateOptions)
        Object.assign(prompts, lastPrompts)
        return submitUrl()
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

    // 从 URL 加载任务（支持刷新页面和分享链接）
    const loadTaskById = async (id: string): Promise<boolean> => {
        // 如果当前已有相同任务在处理中，不重复加载
        if (taskId.value === id) {
            return true
        }

        // 停止之前的轮询和流式
        stopPolling()
        stopStreaming()

        try {
            const data = await getTask(id)
            taskId.value = id
            handleTaskUpdate(data)

            // 根据任务状态决定后续操作
            if (data.status === 'ready_to_stream') {
                // 需要启动流式连接
                startStreaming(id)
            } else if (data.status !== 'completed' && data.status !== 'failed') {
                // 任务仍在进行中，启动轮询
                startPolling(id)
            } else if (data.status === 'completed') {
                handleTaskComplete()
            } else if (data.status === 'failed') {
                handleTaskFailed(data)
            }

            return true
        } catch (error) {
            console.error('加载任务失败:', error)
            return false
        }
    }

    return {
        // 状态
        inputMode,
        url,
        subtitleText,
        subtitleTitle,
        generateOptions,
        isDownloadOnly,
        taskId,
        taskStatus,
        currentTab,
        errorMessage,
        progress,
        result,
        promptsLoaded,
        prompts,
        // 流式状态
        isStreaming,
        streamingOutline,
        streamingArticle,

        // 计算属性
        currentContent,
        displayOutline,
        displayArticle,

        // 方法
        resetState,
        resetSubtitleState,
        loadPrompts,
        savePromptsToStorage,
        resetPrompts,
        resetOutlinePrompts,
        resetArticlePrompts,
        resetPodcastPrompts,
        submitUrl,
        submitSubtitle,
        startNew,
        retryTask,
        copyContent,
        loadTaskById
    }
})

export type TaskStore = ReturnType<typeof useTaskStore>
