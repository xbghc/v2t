import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import { createTask, getTask, getDefaultPrompts, textToPodcast, streamOutline, streamArticle, streamPodcast, streamTaskStatus } from '@/api/task'
import type {
    TaskStatus,
    CurrentTab,
    TaskResult,
    TaskResponse,
    CustomPrompts,
    GenerateOptions,
    InputMode,
    StatusStreamData
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

    // 进度文本（简化为单一字符串）
    const progressText: Ref<string> = ref('准备中...')
    const progressTitle: Ref<string> = ref('')

    // 处理结果
    const result: TaskResult = reactive({
        title: '',
        resource_id: null,
        video_url: null,
        audio_url: null,
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
    // SSE 状态流清理函数
    let statusStreamCleanup: (() => void) | null = null

    // 每种内容的流式状态独立管理
    const outlineStreaming: Ref<boolean> = ref(false)
    const articleStreaming: Ref<boolean> = ref(false)
    const podcastStreaming: Ref<boolean> = ref(false)
    const podcastSynthesizing: Ref<boolean> = ref(false)

    // 流式内容缓冲区
    const streamingOutline: Ref<string> = ref('')
    const streamingArticle: Ref<string> = ref('')
    const streamingPodcast: Ref<string> = ref('')

    // 清理函数
    let outlineCleanup: (() => void) | null = null
    let articleCleanup: (() => void) | null = null
    let podcastCleanup: (() => void) | null = null

    // 计算属性：是否正在流式生成
    const isStreaming: ComputedRef<boolean> = computed(() =>
        outlineStreaming.value || articleStreaming.value || podcastStreaming.value
    )

    // 计算属性：当前内容（用于复制）
    const currentContent: ComputedRef<string> = computed(() => {
        if (currentTab.value === 'article') return result.article || streamingArticle.value || ''
        if (currentTab.value === 'outline') return result.outline || streamingOutline.value || ''
        if (currentTab.value === 'podcast') return result.podcast_script || streamingPodcast.value || ''
        return result.transcript || ''
    })

    // 计算属性：显示内容（优先使用流式内容）
    const displayOutline: ComputedRef<string> = computed(() =>
        outlineStreaming.value ? streamingOutline.value : result.outline
    )
    const displayArticle: ComputedRef<string> = computed(() =>
        articleStreaming.value ? streamingArticle.value : result.article
    )
    const displayPodcast: ComputedRef<string> = computed(() =>
        podcastStreaming.value ? streamingPodcast.value : result.podcast_script
    )

    // 重置状态
    const resetState = (): void => {
        taskId.value = null
        taskStatus.value = 'pending'
        currentTab.value = 'article'
        errorMessage.value = '无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。'
        progressText.value = '准备中...'
        progressTitle.value = ''
        Object.assign(result, { title: '', resource_id: null, video_url: null, audio_url: null, article: '', outline: '', transcript: '', podcast_script: '', has_podcast_audio: false, podcast_error: '' })
        // 重置流式状态
        outlineStreaming.value = false
        articleStreaming.value = false
        podcastStreaming.value = false
        podcastSynthesizing.value = false
        streamingOutline.value = ''
        streamingArticle.value = ''
        streamingPodcast.value = ''
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

    // 停止状态流
    const stopStatusStream = (): void => {
        if (statusStreamCleanup) {
            statusStreamCleanup()
            statusStreamCleanup = null
        }
    }

    // 停止所有流式连接
    const stopAllStreaming = (): void => {
        if (outlineCleanup) {
            outlineCleanup()
            outlineCleanup = null
        }
        if (articleCleanup) {
            articleCleanup()
            articleCleanup = null
        }
        if (podcastCleanup) {
            podcastCleanup()
            podcastCleanup = null
        }
        outlineStreaming.value = false
        articleStreaming.value = false
        podcastStreaming.value = false
        podcastSynthesizing.value = false
    }

    // 检查是否所有流式生成都完成
    const checkAllStreamingDone = (): void => {
        if (!outlineStreaming.value && !articleStreaming.value && !podcastStreaming.value) {
            // 所有流式生成完成
            taskStatus.value = 'completed'
            progressText.value = '处理完成'
            handleTaskComplete()
        }
    }

    // 并行启动所有流式生成
    const startGenerating = (id: string): void => {
        progressText.value = '正在生成内容...'

        // 根据选项并行启动多个流
        if (generateOptions.outline) {
            outlineStreaming.value = true
            streamingOutline.value = ''
            outlineCleanup = streamOutline(
                id,
                (chunk) => { streamingOutline.value += chunk },
                () => {
                    result.outline = streamingOutline.value
                    outlineStreaming.value = false
                    checkAllStreamingDone()
                },
                (err) => {
                    console.error('大纲生成失败:', err)
                    outlineStreaming.value = false
                    checkAllStreamingDone()
                }
            )
        }

        if (generateOptions.article) {
            articleStreaming.value = true
            streamingArticle.value = ''
            articleCleanup = streamArticle(
                id,
                (chunk) => { streamingArticle.value += chunk },
                () => {
                    result.article = streamingArticle.value
                    articleStreaming.value = false
                    checkAllStreamingDone()
                },
                (err) => {
                    console.error('文章生成失败:', err)
                    articleStreaming.value = false
                    checkAllStreamingDone()
                }
            )
        }

        if (generateOptions.podcast) {
            podcastStreaming.value = true
            streamingPodcast.value = ''
            podcastCleanup = streamPodcast(
                id,
                (chunk) => { streamingPodcast.value += chunk },
                () => { /* script done, wait for audio */ },
                () => {
                    podcastSynthesizing.value = true
                    progressText.value = '正在合成播客音频...'
                },
                (hasAudio, audioError) => {
                    result.podcast_script = streamingPodcast.value
                    result.has_podcast_audio = hasAudio
                    if (audioError) result.podcast_error = audioError
                    podcastStreaming.value = false
                    podcastSynthesizing.value = false
                    checkAllStreamingDone()
                },
                (err) => {
                    console.error('播客生成失败:', err)
                    podcastStreaming.value = false
                    podcastSynthesizing.value = false
                    checkAllStreamingDone()
                }
            )
        }

        // 如果没有选择任何生成选项，直接完成
        if (!generateOptions.outline && !generateOptions.article && !generateOptions.podcast) {
            taskStatus.value = 'completed'
            progressText.value = '处理完成'
            handleTaskComplete()
        }
    }

    // 处理 SSE 状态更新
    const handleStatusStreamUpdate = (data: StatusStreamData): void => {
        taskStatus.value = data.status

        // 渐进更新数据
        if (data.title) {
            progressTitle.value = data.title
            result.title = data.title
        }
        if (data.resource_id) result.resource_id = data.resource_id
        if (data.video_url) result.video_url = data.video_url
        if (data.audio_url) result.audio_url = data.audio_url
        if (data.transcript) result.transcript = data.transcript

        // 更新进度文本
        progressText.value = data.progress || getProgressText(data.status)

        // 根据状态处理
        if (data.status === 'ready') {
            // 转录完成，启动流式生成
            stopStatusStream()
            if (taskId.value) {
                startGenerating(taskId.value)
            }
        } else if (data.status === 'completed') {
            stopStatusStream()
            handleTaskComplete()
        } else if (data.status === 'failed') {
            stopStatusStream()
            errorMessage.value = data.error || '处理失败'
        }
    }

    // 启动状态流监听
    const startStatusStream = (id: string): void => {
        taskId.value = id
        stopStatusStream()
        statusStreamCleanup = streamTaskStatus(
            id,
            handleStatusStreamUpdate,
            (err) => {
                console.error('状态流错误:', err)
            }
        )
    }

    // 处理任务更新
    const handleTaskUpdate = (data: TaskResponse): void => {
        taskStatus.value = data.status

        // 渐进更新数据
        if (data.title) {
            progressTitle.value = data.title
            result.title = data.title
        }
        if (data.resource_id) result.resource_id = data.resource_id
        if (data.video_url) result.video_url = data.video_url
        if (data.audio_url) result.audio_url = data.audio_url
        if (data.transcript) result.transcript = data.transcript
        if (data.outline) result.outline = data.outline
        if (data.article) result.article = data.article
        if (data.podcast_script) result.podcast_script = data.podcast_script
        if (data.has_podcast_audio) result.has_podcast_audio = true
        if (data.podcast_error) result.podcast_error = data.podcast_error

        // 更新进度文本
        progressText.value = data.progress || getProgressText(data.status)

        // 自动切换到有内容的 tab
        if (result.transcript && !result.outline && !result.article && !result.podcast_script && currentTab.value !== 'transcript') {
            currentTab.value = 'transcript'
        }
    }

    // 根据状态获取进度文本
    const getProgressText = (status: TaskStatus): string => {
        switch (status) {
        case 'pending': return '等待处理...'
        case 'downloading': return '正在下载视频...'
        case 'transcribing': return '正在转录音频...'
        case 'ready': return '准备生成内容...'
        case 'completed': return '处理完成'
        case 'failed': return '处理失败'
        default: return '处理中...'
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
            startStatusStream(data.task_id)
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
            startStatusStream(data.task_id)
            return data.task_id
        } catch (error) {
            errorMessage.value = (error as Error).message
            taskStatus.value = 'failed'
            return null
        }
    }

    // 开始新任务（重置状态，不处理路由）
    const startNew = (): void => {
        stopStatusStream()
        stopAllStreaming()
        resetState()
        resetSubtitleState()
        url.value = ''
    }

    // 重试任务，返回 task_id 或 null
    const retryTask = async (): Promise<string | null> => {
        stopStatusStream()
        stopAllStreaming()
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
        stopStatusStream()
        stopAllStreaming()

        try {
            const data = await getTask(id)
            taskId.value = id
            handleTaskUpdate(data)

            // 根据任务状态决定后续操作
            if (data.status === 'ready') {
                // 需要启动流式连接
                startGenerating(id)
            } else if (data.status !== 'completed' && data.status !== 'failed') {
                // 任务仍在进行中，启动轮询
                startStatusStream(id)
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
        progressText,
        progressTitle,
        result,
        promptsLoaded,
        prompts,
        // 流式状态
        isStreaming,
        outlineStreaming,
        articleStreaming,
        podcastStreaming,
        podcastSynthesizing,
        streamingOutline,
        streamingArticle,
        streamingPodcast,

        // 计算属性
        currentContent,
        displayOutline,
        displayArticle,
        displayPodcast,

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
