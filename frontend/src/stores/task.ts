import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import {
    createWorkspace,
    getWorkspace,
    getDefaultPrompts,
    streamOutline,
    streamArticle,
    streamPodcast,
    streamZhihuArticle,
    streamWorkspaceStatus
} from '@/api/workspace'
import { useToastStore } from '@/stores/toast'
import type {
    WorkspaceStatus,
    WorkspaceResponse,
    WorkspaceResource,
    CurrentTab,
    CustomPrompts,
    GenerateOptions,
    InputMode,
    StreamPrompts
} from '@/types'

export const useTaskStore = defineStore('task', () => {
    // 输入模式
    const inputMode: Ref<InputMode> = ref('url')

    // 表单输入
    const url: Ref<string> = ref('')

    // 生成选项
    const generateOptions: GenerateOptions = reactive({
        outline: true,
        article: true,
        podcast: false
    })

    // 计算属性：是否仅下载
    const isDownloadOnly: ComputedRef<boolean> = computed(() =>
        !generateOptions.outline && !generateOptions.article && !generateOptions.podcast
    )

    // 工作区状态
    const workspaceId: Ref<string | null> = ref(null)
    const workspaceStatus: Ref<WorkspaceStatus> = ref('pending')
    const currentTab: Ref<CurrentTab> = ref('article')
    const errorMessage: Ref<string> = ref('无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。')

    // 进度文本
    const progressText: Ref<string> = ref('准备中...')
    const progressTitle: Ref<string> = ref('')

    // 工作区资源
    const title: Ref<string> = ref('')
    const videoUrl: Ref<string | null> = ref(null)
    const audioUrl: Ref<string | null> = ref(null)
    const transcript: Ref<string> = ref('')

    // 生成内容结果
    const outline: Ref<string> = ref('')
    const article: Ref<string> = ref('')
    const podcastScript: Ref<string> = ref('')
    const podcastAudioUrl: Ref<string | null> = ref(null)
    const podcastError: Ref<string> = ref('')
    const zhihuArticle: Ref<string> = ref('')

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

    // 计算属性：是否有播客音频
    const hasPodcastAudio: ComputedRef<boolean> = computed(() => !!podcastAudioUrl.value)

    // 计算属性：当前内容（用于复制）
    const currentContent: ComputedRef<string> = computed(() => {
        if (currentTab.value === 'article') return article.value || streamingArticle.value || ''
        if (currentTab.value === 'outline') return outline.value || streamingOutline.value || ''
        if (currentTab.value === 'podcast') return podcastScript.value || streamingPodcast.value || ''
        if (currentTab.value === 'zhihu') return zhihuArticle.value || streamingZhihu.value || ''
        return transcript.value || ''
    })

    // 计算属性：显示内容
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

    // 从资源列表获取内容的辅助函数
    const getResourceContent = (resources: WorkspaceResource[], name: string): string => {
        // 获取最新的资源
        const resource = [...resources].reverse().find(r => r.name === name)
        return resource?.content || ''
    }

    const getResourceUrl = (resources: WorkspaceResource[], name: string): string | null => {
        const resource = [...resources].reverse().find(r => r.name === name)
        return resource?.download_url || null
    }

    // 重置状态
    const resetState = (): void => {
        workspaceId.value = null
        workspaceStatus.value = 'pending'
        currentTab.value = 'article'
        errorMessage.value = '无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。'
        progressText.value = '准备中...'
        progressTitle.value = ''
        title.value = ''
        videoUrl.value = null
        audioUrl.value = null
        transcript.value = ''
        outline.value = ''
        article.value = ''
        podcastScript.value = ''
        podcastAudioUrl.value = null
        podcastError.value = ''
        zhihuArticle.value = ''
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

    // 初始化提示词
    const loadPrompts = async (): Promise<void> => {
        if (promptsLoaded.value) return

        const stored = loadPromptsFromStorage()
        if (stored) {
            Object.assign(prompts, stored)
            promptsLoaded.value = true
            return
        }

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

    // 重置单个提示词
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
            progressText.value = '处理完成'
            handleTaskComplete()
        }
    }

    // 并行启动所有流式生成
    const startGenerating = (wsId: string): void => {
        progressText.value = '正在生成内容...'

        if (generateOptions.outline) {
            outlineStreaming.value = true
            streamingOutline.value = ''
            const outlinePrompts: StreamPrompts = {
                systemPrompt: prompts.outlineSystem,
                userPrompt: prompts.outlineUser
            }
            outlineCleanup = streamOutline(
                wsId,
                outlinePrompts,
                () => { /* resource created */ },
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
                wsId,
                articlePrompts,
                () => { /* resource created */ },
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
                wsId,
                podcastPrompts,
                () => { /* resource created */ },
                (chunk) => { streamingPodcast.value += chunk },
                () => { /* script done */ },
                () => {
                    podcastSynthesizing.value = true
                    progressText.value = '正在合成播客音频...'
                },
                (hasAudio, audioResourceId, audioErr) => {
                    podcastScript.value = streamingPodcast.value
                    if (hasAudio && audioResourceId && workspaceId.value) {
                        podcastAudioUrl.value = `/api/workspaces/${workspaceId.value}/resources/${audioResourceId}`
                    }
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
            progressText.value = '处理完成'
            handleTaskComplete()
        }
    }

    // 更新工作区状态
    const updateWorkspaceState = (data: WorkspaceResponse): void => {
        workspaceStatus.value = data.status
        title.value = data.title
        progressTitle.value = data.title
        progressText.value = data.progress || getProgressText(data.status)

        if (data.error) {
            errorMessage.value = data.error
        }

        // 从资源列表获取内容
        const resources = data.resources
        videoUrl.value = getResourceUrl(resources, 'video')
        audioUrl.value = getResourceUrl(resources, 'audio')
        transcript.value = getResourceContent(resources, 'transcript')

        // 如果已有生成内容，从资源中获取
        if (!outline.value) outline.value = getResourceContent(resources, 'outline')
        if (!article.value) article.value = getResourceContent(resources, 'article')
        if (!podcastScript.value) podcastScript.value = getResourceContent(resources, 'podcast_script')
        if (!zhihuArticle.value) zhihuArticle.value = getResourceContent(resources, 'zhihu')

        // 获取播客音频 URL
        const podcastAudio = getResourceUrl(resources, 'podcast')
        if (podcastAudio) podcastAudioUrl.value = podcastAudio
    }

    // 处理 SSE 状态更新
    const handleStatusStreamUpdate = (data: WorkspaceResponse): void => {
        updateWorkspaceState(data)

        if (data.status === 'ready') {
            stopStatusStream()
            if (workspaceId.value) {
                startGenerating(workspaceId.value)
            }
        } else if (data.status === 'failed') {
            stopStatusStream()
        }
    }

    // 启动状态流监听
    const startStatusStream = (id: string): void => {
        workspaceId.value = id
        stopStatusStream()
        statusStreamCleanup = streamWorkspaceStatus(
            id,
            handleStatusStreamUpdate,
            (err) => {
                console.error('状态流错误:', err)
            }
        )
    }

    // 根据状态获取进度文本
    const getProgressText = (status: WorkspaceStatus): string => {
        switch (status) {
        case 'pending': return '等待处理...'
        case 'downloading': return '正在下载视频...'
        case 'transcribing': return '正在转录音频...'
        case 'ready': return '准备生成内容...'
        case 'failed': return '处理失败'
        default: return '处理中...'
        }
    }

    // 处理任务完成
    const handleTaskComplete = (): void => {
        if (article.value) {
            currentTab.value = 'article'
        } else if (zhihuArticle.value) {
            currentTab.value = 'zhihu'
        } else if (outline.value) {
            currentTab.value = 'outline'
        } else if (podcastScript.value) {
            currentTab.value = 'podcast'
        } else {
            currentTab.value = 'transcript'
        }
    }

    // 提交 URL，返回 workspace_id 或 null
    const submitUrl = async (): Promise<string | null> => {
        const toastStore = useToastStore()
        if (!url.value.trim()) {
            toastStore.showToast('请输入视频链接', 'warning')
            return null
        }

        lastUrl = url.value
        savePromptsToStorage()
        resetState()

        try {
            const data = await createWorkspace(url.value)
            startStatusStream(data.workspace_id)
            return data.workspace_id
        } catch (error) {
            errorMessage.value = (error as Error).message
            workspaceStatus.value = 'failed'
            return null
        }
    }

    // 开始新任务
    const startNew = (): void => {
        stopStatusStream()
        stopAllStreaming()
        resetState()
        url.value = ''
    }

    // 重试任务
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
        if (!workspaceId.value) return

        const wsId = workspaceId.value

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
                wsId,
                outlinePrompts,
                () => {},
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
                wsId,
                articlePrompts,
                () => {},
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
                wsId,
                podcastPrompts,
                () => {},
                (chunk) => { streamingPodcast.value += chunk },
                () => {},
                () => { podcastSynthesizing.value = true },
                (hasAudio, audioResourceId, audioErr) => {
                    podcastScript.value = streamingPodcast.value
                    if (hasAudio && audioResourceId && workspaceId.value) {
                        podcastAudioUrl.value = `/api/workspaces/${workspaceId.value}/resources/${audioResourceId}`
                    }
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
                wsId,
                zhihuPrompts,
                () => {},
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

    // 从 URL 加载工作区
    const loadWorkspaceById = async (id: string): Promise<boolean> => {
        if (workspaceId.value === id) {
            return true
        }

        stopStatusStream()
        stopAllStreaming()

        try {
            const data = await getWorkspace(id)
            workspaceId.value = id
            updateWorkspaceState(data)

            if (data.status === 'ready') {
                startGenerating(id)
            } else if (data.status !== 'failed') {
                startStatusStream(id)
            }

            return true
        } catch (error) {
            console.error('加载工作区失败:', error)
            return false
        }
    }

    return {
        // 状态
        inputMode,
        url,
        generateOptions,
        isDownloadOnly,
        workspaceId,
        workspaceStatus,
        currentTab,
        errorMessage,
        progressText,
        progressTitle,
        title,
        videoUrl,
        audioUrl,
        transcript,
        // 生成内容
        outline,
        article,
        podcastScript,
        podcastAudioUrl,
        podcastError,
        zhihuArticle,
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
        // 播客音频状态
        hasPodcastAudio,
        // 计算属性
        currentContent,
        displayOutline,
        displayArticle,
        displayPodcast,
        displayZhihu,
        // 方法
        resetState,
        loadPrompts,
        savePromptsToStorage,
        resetPrompts,
        resetOutlinePrompts,
        resetArticlePrompts,
        resetPodcastPrompts,
        resetZhihuPrompts,
        submitUrl,
        startNew,
        retryTask,
        copyContent,
        loadWorkspaceById,
        generateSingleContent
    }
})

export type TaskStore = ReturnType<typeof useTaskStore>
