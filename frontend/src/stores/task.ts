import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import {
    createVideoTask,
    getVideoTask,
    getDefaultPrompts,
    createPodcastTask,
    streamOutline,
    streamArticle,
    streamPodcast,
    streamZhihuArticle,
    streamVideoTaskStatus
} from '@/api/task'
import { useToastStore } from '@/stores/toast'
import type {
    TaskStatus,
    CurrentTab,
    VideoTaskResult,
    VideoTaskResponse,
    CustomPrompts,
    GenerateOptions,
    InputMode,
    VideoStatusStreamData,
    StreamPrompts
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

    // 视频任务结果
    const videoResult: VideoTaskResult = reactive({
        title: '',
        resource_id: null,
        video_url: null,
        audio_url: null,
        transcript: ''
    })

    // 生成内容结果
    const outline: Ref<string> = ref('')
    const article: Ref<string> = ref('')
    const podcastScript: Ref<string> = ref('')
    const hasPodcastAudio: Ref<boolean> = ref(false)
    const podcastError: Ref<string> = ref('')
    const zhihuArticle: Ref<string> = ref('')

    // 各任务 ID
    const outlineTaskId: Ref<string | null> = ref(null)
    const articleTaskId: Ref<string | null> = ref(null)
    const podcastTaskId: Ref<string | null> = ref(null)
    const zhihuTaskId: Ref<string | null> = ref(null)

    // 提示词状态
    const promptsLoaded: Ref<boolean> = ref(false)
    const prompts: CustomPrompts = reactive({
        outlineSystem: '',
        outlineUser: '',
        articleSystem: '',
        articleUser: '',
        podcastSystem: '',
        podcastUser: '',
        zhihuSystem: '',
        zhihuUser: ''
    })

    // localStorage key
    const PROMPTS_STORAGE_KEY = 'v2t_custom_prompts'

    // 保存最后一次提交的参数，用于重试
    let lastUrl: string = ''
    // SSE 状态流清理函数
    let statusStreamCleanup: (() => void) | null = null

    // 每种内容的流式状态独立管理
    const outlineStreaming: Ref<boolean> = ref(false)
    const articleStreaming: Ref<boolean> = ref(false)
    const podcastStreaming: Ref<boolean> = ref(false)
    const podcastSynthesizing: Ref<boolean> = ref(false)
    const zhihuStreaming: Ref<boolean> = ref(false)

    // 生成失败状态跟踪
    const outlineFailed: Ref<boolean> = ref(false)
    const articleFailed: Ref<boolean> = ref(false)
    const podcastFailed: Ref<boolean> = ref(false)
    const zhihuFailed: Ref<boolean> = ref(false)

    // 流式内容缓冲区
    const streamingOutline: Ref<string> = ref('')
    const streamingArticle: Ref<string> = ref('')
    const streamingPodcast: Ref<string> = ref('')
    const streamingZhihu: Ref<string> = ref('')

    // 清理函数
    let outlineCleanup: (() => void) | null = null
    let articleCleanup: (() => void) | null = null
    let podcastCleanup: (() => void) | null = null
    let zhihuCleanup: (() => void) | null = null

    // 计算属性：是否正在流式生成
    const isStreaming: ComputedRef<boolean> = computed(() =>
        outlineStreaming.value || articleStreaming.value || podcastStreaming.value || zhihuStreaming.value
    )

    // 计算属性：当前内容（用于复制）
    const currentContent: ComputedRef<string> = computed(() => {
        if (currentTab.value === 'article') return article.value || streamingArticle.value || ''
        if (currentTab.value === 'outline') return outline.value || streamingOutline.value || ''
        if (currentTab.value === 'podcast') return podcastScript.value || streamingPodcast.value || ''
        return videoResult.transcript || ''
    })

    // 计算属性：显示内容（优先使用流式内容）
    const displayOutline: ComputedRef<string> = computed(() =>
        outlineStreaming.value ? streamingOutline.value : outline.value
    )
    const displayArticle: ComputedRef<string> = computed(() =>
        articleStreaming.value ? streamingArticle.value : article.value
    )
    const displayPodcast: ComputedRef<string> = computed(() =>
        podcastStreaming.value ? streamingPodcast.value : podcastScript.value
    )
    const displayZhihu: ComputedRef<string> = computed(() =>
        zhihuStreaming.value ? streamingZhihu.value : zhihuArticle.value
    )

    // 重置状态
    const resetState = (): void => {
        taskId.value = null
        taskStatus.value = 'pending'
        currentTab.value = 'article'
        errorMessage.value = '无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。'
        progressText.value = '准备中...'
        progressTitle.value = ''
        // 重置视频结果
        Object.assign(videoResult, { title: '', resource_id: null, video_url: null, audio_url: null, transcript: '' })
        // 重置生成内容
        outline.value = ''
        article.value = ''
        podcastScript.value = ''
        hasPodcastAudio.value = false
        podcastError.value = ''
        zhihuArticle.value = ''
        // 重置任务 ID
        outlineTaskId.value = null
        articleTaskId.value = null
        podcastTaskId.value = null
        zhihuTaskId.value = null
        // 重置流式状态
        outlineStreaming.value = false
        articleStreaming.value = false
        podcastStreaming.value = false
        podcastSynthesizing.value = false
        zhihuStreaming.value = false
        streamingOutline.value = ''
        streamingArticle.value = ''
        streamingPodcast.value = ''
        streamingZhihu.value = ''
        // 重置失败状态
        outlineFailed.value = false
        articleFailed.value = false
        podcastFailed.value = false
        zhihuFailed.value = false
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
            prompts.zhihuSystem = defaults.zhihu_system
            prompts.zhihuUser = defaults.zhihu_user
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
            prompts.zhihuSystem = defaults.zhihu_system
            prompts.zhihuUser = defaults.zhihu_user
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

    // 重置知乎提示词
    const resetZhihuPrompts = async (): Promise<void> => {
        try {
            const defaults = await getDefaultPrompts()
            prompts.zhihuSystem = defaults.zhihu_system
            prompts.zhihuUser = defaults.zhihu_user
            savePromptsToStorage()
        } catch (error) {
            console.error('重置知乎提示词失败:', error)
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
        if (zhihuCleanup) {
            zhihuCleanup()
            zhihuCleanup = null
        }
        outlineStreaming.value = false
        articleStreaming.value = false
        podcastStreaming.value = false
        podcastSynthesizing.value = false
        zhihuStreaming.value = false
    }

    // 检查是否所有流式生成都完成
    const checkAllStreamingDone = (): void => {
        if (!outlineStreaming.value && !articleStreaming.value && !podcastStreaming.value && !zhihuStreaming.value) {
            // 所有流式生成完成
            taskStatus.value = 'completed'
            progressText.value = '处理完成'
            handleTaskComplete()
        }
    }

    // 并行启动所有流式生成
    const startGenerating = (videoTaskIdStr: string): void => {
        progressText.value = '正在生成内容...'

        // 根据选项并行启动多个流
        if (generateOptions.outline) {
            outlineStreaming.value = true
            streamingOutline.value = ''
            const outlinePrompts: StreamPrompts = {
                systemPrompt: prompts.outlineSystem,
                userPrompt: prompts.outlineUser
            }
            outlineCleanup = streamOutline(
                videoTaskIdStr,
                outlinePrompts,
                (newTaskId) => { outlineTaskId.value = newTaskId },
                (chunk) => { streamingOutline.value += chunk },
                () => {
                    outline.value = streamingOutline.value
                    outlineStreaming.value = false
                    checkAllStreamingDone()
                },
                (err) => {
                    console.error('大纲生成失败:', err)
                    outlineFailed.value = true
                    outlineStreaming.value = false
                    checkAllStreamingDone()
                }
            )
        }

        if (generateOptions.article) {
            articleStreaming.value = true
            streamingArticle.value = ''
            const articlePrompts: StreamPrompts = {
                systemPrompt: prompts.articleSystem,
                userPrompt: prompts.articleUser
            }
            articleCleanup = streamArticle(
                videoTaskIdStr,
                articlePrompts,
                (newTaskId) => { articleTaskId.value = newTaskId },
                (chunk) => { streamingArticle.value += chunk },
                () => {
                    article.value = streamingArticle.value
                    articleStreaming.value = false
                    checkAllStreamingDone()
                },
                (err) => {
                    console.error('文章生成失败:', err)
                    articleFailed.value = true
                    articleStreaming.value = false
                    checkAllStreamingDone()
                }
            )
        }

        if (generateOptions.podcast) {
            podcastStreaming.value = true
            streamingPodcast.value = ''
            const podcastPrompts: StreamPrompts = {
                systemPrompt: prompts.podcastSystem,
                userPrompt: prompts.podcastUser
            }
            podcastCleanup = streamPodcast(
                videoTaskIdStr,
                podcastPrompts,
                (newTaskId) => { podcastTaskId.value = newTaskId },
                (chunk) => { streamingPodcast.value += chunk },
                () => { /* script done, wait for audio */ },
                () => {
                    podcastSynthesizing.value = true
                    progressText.value = '正在合成播客音频...'
                },
                (hasAudio, audioErr) => {
                    podcastScript.value = streamingPodcast.value
                    hasPodcastAudio.value = hasAudio
                    if (audioErr) podcastError.value = audioErr
                    podcastStreaming.value = false
                    podcastSynthesizing.value = false
                    checkAllStreamingDone()
                },
                (err) => {
                    console.error('播客生成失败:', err)
                    podcastFailed.value = true
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
    const handleStatusStreamUpdate = (data: VideoStatusStreamData): void => {
        taskStatus.value = data.status

        // 渐进更新数据
        if (data.title) {
            progressTitle.value = data.title
            videoResult.title = data.title
        }
        if (data.resource_id) videoResult.resource_id = data.resource_id
        if (data.video_url) videoResult.video_url = data.video_url
        if (data.audio_url) videoResult.audio_url = data.audio_url
        if (data.transcript) videoResult.transcript = data.transcript

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
        statusStreamCleanup = streamVideoTaskStatus(
            id,
            handleStatusStreamUpdate,
            (err) => {
                console.error('状态流错误:', err)
            }
        )
    }

    // 处理视频任务更新
    const handleVideoTaskUpdate = (data: VideoTaskResponse): void => {
        taskStatus.value = data.status

        // 渐进更新数据
        if (data.title) {
            progressTitle.value = data.title
            videoResult.title = data.title
        }
        if (data.resource_id) videoResult.resource_id = data.resource_id
        if (data.video_url) videoResult.video_url = data.video_url
        if (data.audio_url) videoResult.audio_url = data.audio_url
        if (data.transcript) videoResult.transcript = data.transcript

        // 更新进度文本
        progressText.value = data.progress || getProgressText(data.status)

        // 自动切换到有内容的 tab
        if (videoResult.transcript && !outline.value && !article.value && !podcastScript.value && currentTab.value !== 'transcript') {
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
        if (article.value) {
            currentTab.value = 'article'
        } else if (zhihuArticle.value) {
            currentTab.value = 'article' // 知乎文章也归类到文章类
        } else if (outline.value) {
            currentTab.value = 'outline'
        } else if (podcastScript.value) {
            currentTab.value = 'podcast'
        } else {
            currentTab.value = 'transcript'
        }
    }

    // 处理任务失败
    const handleTaskFailed = (data: VideoTaskResponse): void => {
        errorMessage.value = data.error || '处理失败'
    }

    // 提交 URL，返回 task_id 或 null（失败时）
    const submitUrl = async (): Promise<string | null> => {
        const toastStore = useToastStore()
        if (!url.value.trim()) {
            toastStore.showToast('请输入视频链接', 'warning')
            return null
        }

        lastUrl = url.value
        // 保存当前提示词到 localStorage
        savePromptsToStorage()
        resetState()

        try {
            const data = await createVideoTask(url.value)
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
        const toastStore = useToastStore()
        if (!subtitleText.value.trim() || subtitleText.value.length < 10) {
            toastStore.showToast('请上传字幕文件', 'warning')
            return null
        }

        // 保存当前提示词到 localStorage
        savePromptsToStorage()
        resetState()
        // 设置字幕模式的错误信息
        errorMessage.value = '生成播客失败，请检查字幕内容是否正确，或尝试其他内容。'
        // 切换到播客 tab
        currentTab.value = 'podcast'

        try {
            const data = await createPodcastTask(
                subtitleText.value,
                subtitleTitle.value,
                prompts.podcastSystem,
                prompts.podcastUser
            )
            // 播客任务也需要监听状态流
            taskId.value = data.task_id
            podcastTaskId.value = data.task_id
            taskStatus.value = data.status
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
        return submitUrl()
    }

    // 复制当前内容
    const copyContent = (): void => {
        if (!currentContent.value) return
        const toastStore = useToastStore()
        navigator.clipboard.writeText(currentContent.value).then(() => {
            toastStore.showToast('已复制到剪贴板', 'success')
        }).catch(() => {
            toastStore.showToast('复制失败，请手动选择复制', 'error')
        })
    }

    // 生成单个内容类型
    const generateSingleContent = (type: 'outline' | 'article' | 'podcast' | 'zhihu'): void => {
        if (!taskId.value) return

        const videoTaskIdStr = taskId.value

        if (type === 'outline' && !outlineStreaming.value) {
            generateOptions.outline = true
            outlineFailed.value = false
            outlineStreaming.value = true
            streamingOutline.value = ''
            const outlinePrompts: StreamPrompts = {
                systemPrompt: prompts.outlineSystem,
                userPrompt: prompts.outlineUser
            }
            outlineCleanup = streamOutline(
                videoTaskIdStr,
                outlinePrompts,
                (newTaskId) => { outlineTaskId.value = newTaskId },
                (chunk) => { streamingOutline.value += chunk },
                () => {
                    outline.value = streamingOutline.value
                    outlineStreaming.value = false
                },
                (err) => {
                    console.error('大纲生成失败:', err)
                    outlineFailed.value = true
                    outlineStreaming.value = false
                }
            )
        }

        if (type === 'article' && !articleStreaming.value) {
            generateOptions.article = true
            articleFailed.value = false
            articleStreaming.value = true
            streamingArticle.value = ''
            const articlePrompts: StreamPrompts = {
                systemPrompt: prompts.articleSystem,
                userPrompt: prompts.articleUser
            }
            articleCleanup = streamArticle(
                videoTaskIdStr,
                articlePrompts,
                (newTaskId) => { articleTaskId.value = newTaskId },
                (chunk) => { streamingArticle.value += chunk },
                () => {
                    article.value = streamingArticle.value
                    articleStreaming.value = false
                },
                (err) => {
                    console.error('文章生成失败:', err)
                    articleFailed.value = true
                    articleStreaming.value = false
                }
            )
        }

        if (type === 'podcast' && !podcastStreaming.value) {
            generateOptions.podcast = true
            podcastFailed.value = false
            podcastStreaming.value = true
            streamingPodcast.value = ''
            const podcastPrompts: StreamPrompts = {
                systemPrompt: prompts.podcastSystem,
                userPrompt: prompts.podcastUser
            }
            podcastCleanup = streamPodcast(
                videoTaskIdStr,
                podcastPrompts,
                (newTaskId) => { podcastTaskId.value = newTaskId },
                (chunk) => { streamingPodcast.value += chunk },
                () => { /* script done, wait for audio */ },
                () => {
                    podcastSynthesizing.value = true
                },
                (hasAudio, audioErr) => {
                    podcastScript.value = streamingPodcast.value
                    hasPodcastAudio.value = hasAudio
                    if (audioErr) podcastError.value = audioErr
                    podcastStreaming.value = false
                    podcastSynthesizing.value = false
                },
                (err) => {
                    console.error('播客生成失败:', err)
                    podcastFailed.value = true
                    podcastStreaming.value = false
                    podcastSynthesizing.value = false
                }
            )
        }

        if (type === 'zhihu' && !zhihuStreaming.value) {
            zhihuFailed.value = false
            zhihuStreaming.value = true
            streamingZhihu.value = ''
            const zhihuPrompts: StreamPrompts = {
                systemPrompt: prompts.zhihuSystem,
                userPrompt: prompts.zhihuUser
            }
            zhihuCleanup = streamZhihuArticle(
                videoTaskIdStr,
                zhihuPrompts,
                (newTaskId) => { zhihuTaskId.value = newTaskId },
                (chunk) => { streamingZhihu.value += chunk },
                () => {
                    zhihuArticle.value = streamingZhihu.value
                    zhihuStreaming.value = false
                },
                (err) => {
                    console.error('知乎文章生成失败:', err)
                    zhihuFailed.value = true
                    zhihuStreaming.value = false
                }
            )
        }
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
            const data = await getVideoTask(id)
            taskId.value = id
            handleVideoTaskUpdate(data)

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
        videoResult,
        // 生成内容
        outline,
        article,
        podcastScript,
        hasPodcastAudio,
        podcastError,
        zhihuArticle,
        // 各任务 ID
        outlineTaskId,
        articleTaskId,
        podcastTaskId,
        zhihuTaskId,
        promptsLoaded,
        prompts,
        // 流式状态
        isStreaming,
        outlineStreaming,
        articleStreaming,
        podcastStreaming,
        podcastSynthesizing,
        zhihuStreaming,
        streamingOutline,
        streamingArticle,
        streamingPodcast,
        streamingZhihu,
        // 失败状态
        outlineFailed,
        articleFailed,
        podcastFailed,
        zhihuFailed,

        // 计算属性
        currentContent,
        displayOutline,
        displayArticle,
        displayPodcast,
        displayZhihu,

        // 方法
        resetState,
        resetSubtitleState,
        loadPrompts,
        savePromptsToStorage,
        resetPrompts,
        resetOutlinePrompts,
        resetArticlePrompts,
        resetPodcastPrompts,
        resetZhihuPrompts,
        submitUrl,
        submitSubtitle,
        startNew,
        retryTask,
        copyContent,
        loadTaskById,
        generateSingleContent
    }
})

export type TaskStore = ReturnType<typeof useTaskStore>
