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
import {
    createWorkspaceMachine,
    createContentMachine,
    createInitialWorkspaceContext,
    createInitialContentContext,
} from '@/machines'
import type { WorkspaceEvent, WorkspaceContext, ContentEvent, ContentContext, ContentState } from '@/machines'
import type {
    WorkspaceStatus,
    WorkspaceResponse,
    WorkspaceResource,
    ContentType,
    CurrentTab,
    CustomPrompts,
    GenerateOptions,
    InputMode,
    StreamPrompts
} from '@/types'

// 所有内容类型
const CONTENT_TYPES: ContentType[] = ['outline', 'article', 'podcast', 'zhihu']

// 流式 API 函数映射（outline/article/zhihu 共用签名）
const SIMPLE_STREAM_FN = {
    outline: streamOutline,
    article: streamArticle,
    zhihu: streamZhihuArticle,
} as const

// 提示词字段映射
const PROMPT_KEYS: Record<ContentType, { system: keyof CustomPrompts; user: keyof CustomPrompts }> = {
    outline: { system: 'outlineSystem', user: 'outlineUser' },
    article: { system: 'articleSystem', user: 'articleUser' },
    podcast: { system: 'podcastSystem', user: 'podcastUser' },
    zhihu:   { system: 'zhihuSystem', user: 'zhihuUser' },
}

export const useTaskStore = defineStore('task', () => {
    // ==================== 状态机实例 ====================

    const workspaceMachine = createWorkspaceMachine()
    const contentMachines = {
        outline: createContentMachine('outline'),
        article: createContentMachine('article'),
        podcast: createContentMachine('podcast'),
        zhihu:   createContentMachine('zhihu'),
    } as const

    // ==================== 响应式状态（机器状态的 Vue 包装）====================

    const wsState = ref(workspaceMachine.getState())
    const wsCtx = reactive<WorkspaceContext>({ ...createInitialWorkspaceContext() })

    const contentStates = reactive<Record<ContentType, ContentState>>({
        outline: 'idle', article: 'idle', podcast: 'idle', zhihu: 'idle',
    })
    const contentCtxs = reactive<Record<ContentType, ContentContext>>({
        outline: { ...createInitialContentContext() },
        article: { ...createInitialContentContext() },
        podcast: { ...createInitialContentContext() },
        zhihu:   { ...createInitialContentContext() },
    })

    // ==================== 机器事件发送 ====================

    function sendWorkspace(event: WorkspaceEvent): void {
        const result = workspaceMachine.send(event)
        wsState.value = result.state
        Object.assign(wsCtx, result.context)
    }

    function sendContent(type: ContentType, event: ContentEvent): void {
        const result = contentMachines[type].send(event)
        contentStates[type] = result.state
        Object.assign(contentCtxs[type], result.context)
    }

    // ==================== 非机器状态 ====================

    const inputMode: Ref<InputMode> = ref('url')
    const url: Ref<string> = ref('')
    const currentTab: Ref<CurrentTab> = ref('article')

    const generateOptions: GenerateOptions = reactive({
        outline: true,
        article: true,
        podcast: false,
    })

    const promptsLoaded: Ref<boolean> = ref(false)
    const prompts: CustomPrompts = reactive({
        outlineSystem: '', outlineUser: '',
        articleSystem: '', articleUser: '',
        podcastSystem: '', podcastUser: '',
        zhihuSystem: '', zhihuUser: '',
    })

    const PROMPTS_STORAGE_KEY = 'v2t_custom_prompts'
    let lastUrl = ''

    // SSE / 流式清理函数
    let statusStreamCleanup: (() => void) | null = null
    const streamCleanups: Record<ContentType, (() => void) | null> = {
        outline: null, article: null, podcast: null, zhihu: null,
    }

    // 生成是否已启动的标记（替代 workspace generating 状态）
    let generationStarted = false

    // ==================== 向后兼容的 computed 属性 ====================

    // 工作区状态 → 后端 WorkspaceStatus（组件继续用这个值）
    const workspaceStatus: ComputedRef<WorkspaceStatus> = computed(() => {
        const s = wsState.value
        if (s === 'idle') return 'pending'
        return s  // 1:1 映射
    })

    const isDownloadOnly: ComputedRef<boolean> = computed(() =>
        !generateOptions.outline && !generateOptions.article && !generateOptions.podcast
    )

    // 派生 computed（替代 generating/completed 状态）
    const isGenerating: ComputedRef<boolean> = computed(() =>
        CONTENT_TYPES.some(t =>
            contentStates[t] === 'streaming' || contentStates[t] === 'synthesizing'
        )
    )

    const hasGeneratedContent: ComputedRef<boolean> = computed(() =>
        CONTENT_TYPES.some(t => !!contentCtxs[t].finalContent)
    )

    // 工作区 context
    const workspaceId = computed(() => wsCtx.workspaceId)
    const title = computed(() => wsCtx.title)
    const progressText = computed(() => wsCtx.progressText)
    const progressTitle = computed(() => wsCtx.progressTitle)
    const errorMessage = computed(() => wsCtx.errorMessage)
    const videoUrl = computed(() => wsCtx.videoUrl)
    const audioUrl = computed(() => wsCtx.audioUrl)
    const transcript = computed(() => wsCtx.transcript)

    // 内容流式状态
    const outlineStreaming = computed(() => contentStates.outline === 'streaming')
    const articleStreaming = computed(() => contentStates.article === 'streaming')
    const podcastStreaming = computed(() =>
        contentStates.podcast === 'streaming' || contentStates.podcast === 'synthesizing'
    )
    const podcastSynthesizing = computed(() => contentStates.podcast === 'synthesizing')
    const zhihuStreaming = computed(() => contentStates.zhihu === 'streaming')

    // 内容失败状态
    const outlineFailed = computed(() => contentStates.outline === 'failed')
    const articleFailed = computed(() => contentStates.article === 'failed')
    const podcastFailed = computed(() => contentStates.podcast === 'failed')
    const zhihuFailed = computed(() => contentStates.zhihu === 'failed')

    // 最终内容
    const outline = computed(() => contentCtxs.outline.finalContent)
    const article = computed(() => contentCtxs.article.finalContent)
    const podcastScript = computed(() => contentCtxs.podcast.finalContent)
    const zhihuArticle = computed(() => contentCtxs.zhihu.finalContent)

    // 流式缓冲区
    const streamingOutline = computed(() => contentCtxs.outline.streamBuffer)
    const streamingArticle = computed(() => contentCtxs.article.streamBuffer)
    const streamingPodcast = computed(() => contentCtxs.podcast.streamBuffer)
    const streamingZhihu = computed(() => contentCtxs.zhihu.streamBuffer)

    // 播客专属
    const podcastAudioUrl = computed(() => contentCtxs.podcast.audioUrl)
    const podcastError = computed(() => contentCtxs.podcast.audioError)
    const hasPodcastAudio: ComputedRef<boolean> = computed(() => !!contentCtxs.podcast.audioUrl)

    // 聚合状态
    const isStreaming: ComputedRef<boolean> = computed(() =>
        CONTENT_TYPES.some(t => contentStates[t] === 'streaming' || contentStates[t] === 'synthesizing')
    )

    // 显示内容（流式优先，完成后显示最终版）
    const displayOutline = computed(() =>
        contentStates.outline === 'streaming' ? contentCtxs.outline.streamBuffer : contentCtxs.outline.finalContent
    )
    const displayArticle = computed(() =>
        contentStates.article === 'streaming' ? contentCtxs.article.streamBuffer : contentCtxs.article.finalContent
    )
    const displayPodcast = computed(() =>
        contentStates.podcast === 'streaming' || contentStates.podcast === 'synthesizing'
            ? contentCtxs.podcast.streamBuffer : contentCtxs.podcast.finalContent
    )
    const displayZhihu = computed(() =>
        contentStates.zhihu === 'streaming' ? contentCtxs.zhihu.streamBuffer : contentCtxs.zhihu.finalContent
    )

    // 当前标签内容（用于复制）
    const currentContent: ComputedRef<string> = computed(() => {
        if (currentTab.value === 'article') return article.value || streamingArticle.value || ''
        if (currentTab.value === 'outline') return outline.value || streamingOutline.value || ''
        if (currentTab.value === 'podcast') return podcastScript.value || streamingPodcast.value || ''
        if (currentTab.value === 'zhihu') return zhihuArticle.value || streamingZhihu.value || ''
        return transcript.value || ''
    })

    // ==================== 辅助函数 ====================

    const getResourceContent = (resources: WorkspaceResource[], name: string): string => {
        const resource = [...resources].reverse().find(r => r.name === name)
        return resource?.content || ''
    }

    const getResourceUrl = (resources: WorkspaceResource[], name: string): string | null => {
        const resource = [...resources].reverse().find(r => r.name === name)
        return resource?.download_url || null
    }

    function getPromptsForType(type: ContentType): StreamPrompts {
        const keys = PROMPT_KEYS[type]
        return { systemPrompt: prompts[keys.system], userPrompt: prompts[keys.user] }
    }

    function shouldAutoGenerate(type: ContentType): boolean {
        if (type === 'outline') return generateOptions.outline
        if (type === 'article') return generateOptions.article
        if (type === 'podcast') return generateOptions.podcast
        return false // zhihu 始终手动触发
    }

    // ==================== SSE / 流式管理 ====================

    const stopStatusStream = (): void => {
        if (statusStreamCleanup) {
            statusStreamCleanup()
            statusStreamCleanup = null
        }
    }

    const stopAllStreaming = (): void => {
        for (const type of CONTENT_TYPES) {
            if (streamCleanups[type]) {
                streamCleanups[type]!()
                streamCleanups[type] = null
            }
        }
    }

    // ==================== 核心流式逻辑 ====================

    function startSingleContentStream(wsId: string, type: ContentType): void {
        // 如果已在流式中，不重复启动
        if (contentStates[type] === 'streaming' || contentStates[type] === 'synthesizing') return

        sendContent(type, { type: 'START' })
        const promptPair = getPromptsForType(type)

        if (type === 'podcast') {
            streamCleanups.podcast = streamPodcast(
                wsId,
                promptPair,
                () => {},
                (chunk) => sendContent('podcast', { type: 'CHUNK', content: chunk }),
                () => {},
                () => sendContent('podcast', { type: 'SYNTHESIZE_START' }),
                (hasAudio, audioResourceId, audioErr) => {
                    sendContent('podcast', {
                        type: 'COMPLETE',
                        audioUrl: hasAudio && audioResourceId
                            ? `/api/workspaces/${wsId}/resources/${audioResourceId}`
                            : undefined,
                        audioError: audioErr,
                    })
                    checkAllStreamingDone()
                },
                (err) => {
                    console.error('播客生成失败:', err)
                    sendContent('podcast', { type: 'FAIL', error: err })
                    checkAllStreamingDone()
                }
            )
        } else {
            const streamFn = SIMPLE_STREAM_FN[type]
            streamCleanups[type] = streamFn(
                wsId,
                promptPair,
                () => {},
                (chunk) => sendContent(type, { type: 'CHUNK', content: chunk }),
                () => {
                    sendContent(type, { type: 'COMPLETE' })
                    checkAllStreamingDone()
                },
                (err) => {
                    console.error(`${type}生成失败:`, err)
                    sendContent(type, { type: 'FAIL', error: err })
                    checkAllStreamingDone()
                }
            )
        }
    }

    function startGenerating(wsId: string): void {
        generationStarted = true

        let started = false
        for (const type of CONTENT_TYPES) {
            if (shouldAutoGenerate(type)) {
                startSingleContentStream(wsId, type)
                started = true
            }
        }

        if (!started) {
            generationStarted = false
            handleTaskComplete()
        }
    }

    function checkAllStreamingDone(): void {
        const allDone = CONTENT_TYPES.every(t => {
            const s = contentStates[t]
            return s === 'idle' || s === 'done' || s === 'failed'
        })
        if (allDone && generationStarted) {
            generationStarted = false
            handleTaskComplete()
        }
    }

    // ==================== 工作区状态更新 ====================

    const updateWorkspaceState = (data: WorkspaceResponse): void => {
        // 更新工作区机器状态
        sendWorkspace({
            type: 'STATUS_UPDATE',
            status: data.status,
            error: data.error || undefined,
        })

        // 更新资源数据
        const resources = data.resources
        sendWorkspace({
            type: 'UPDATE_RESOURCES',
            title: data.title,
            videoUrl: getResourceUrl(resources, 'video'),
            audioUrl: getResourceUrl(resources, 'audio'),
            transcript: getResourceContent(resources, 'transcript'),
            progressText: data.progress || undefined,
        })

        // 加载已有的生成内容到内容机器
        const contentMap: Record<ContentType, string> = {
            outline: getResourceContent(resources, 'outline'),
            article: getResourceContent(resources, 'article'),
            podcast: getResourceContent(resources, 'podcast_script'),
            zhihu: getResourceContent(resources, 'zhihu'),
        }
        for (const type of CONTENT_TYPES) {
            if (contentMap[type] && contentStates[type] === 'idle') {
                // 手动设置 finalContent，不经过 streaming 流程
                contentCtxs[type].finalContent = contentMap[type]
            }
        }

        // 播客音频 URL
        const podcastAudioResource = getResourceUrl(resources, 'podcast')
        if (podcastAudioResource) {
            contentCtxs.podcast.audioUrl = podcastAudioResource
        }
    }

    const handleStatusStreamUpdate = (data: WorkspaceResponse): void => {
        updateWorkspaceState(data)

        if (data.status === 'ready') {
            stopStatusStream()
            startGenerating(wsCtx.workspaceId!)
        } else if (data.status === 'failed') {
            stopStatusStream()
        }
    }

    const startStatusStream = (id: string): void => {
        stopStatusStream()
        statusStreamCleanup = streamWorkspaceStatus(
            id,
            handleStatusStreamUpdate,
            (err) => console.error('状态流错误:', err)
        )
    }

    // ==================== 任务完成处理 ====================

    const handleTaskComplete = (): void => {
        if (contentCtxs.article.finalContent) {
            currentTab.value = 'article'
        } else if (contentCtxs.zhihu.finalContent) {
            currentTab.value = 'zhihu'
        } else if (contentCtxs.outline.finalContent) {
            currentTab.value = 'outline'
        } else if (contentCtxs.podcast.finalContent) {
            currentTab.value = 'podcast'
        } else {
            currentTab.value = 'transcript'
        }
    }

    // ==================== 重置 ====================

    const resetState = (): void => {
        sendWorkspace({ type: 'RESET' })
        for (const type of CONTENT_TYPES) {
            sendContent(type, { type: 'RESET' })
        }
        generationStarted = false
        currentTab.value = 'article'
    }

    // ==================== 提示词管理（不变）====================

    const loadPromptsFromStorage = (): CustomPrompts | null => {
        try {
            const stored = localStorage.getItem(PROMPTS_STORAGE_KEY)
            if (stored) return JSON.parse(stored) as CustomPrompts
        } catch (error) {
            console.error('读取 localStorage 失败:', error)
        }
        return null
    }

    const savePromptsToStorage = (): void => {
        try {
            localStorage.setItem(PROMPTS_STORAGE_KEY, JSON.stringify(prompts))
        } catch (error) {
            console.error('保存到 localStorage 失败:', error)
        }
    }

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

    // ==================== 公共操作 ====================

    const submitUrl = async (): Promise<string | null> => {
        const toastStore = useToastStore()
        if (!url.value.trim()) {
            toastStore.showToast('请输入视频链接', 'warning')
            return null
        }

        lastUrl = url.value
        savePromptsToStorage()
        stopStatusStream()
        stopAllStreaming()
        resetState()

        try {
            const data = await createWorkspace(url.value)
            sendWorkspace({ type: 'SUBMIT', workspaceId: data.workspace_id })
            startStatusStream(data.workspace_id)
            return data.workspace_id
        } catch (error) {
            sendWorkspace({ type: 'FAIL', error: (error as Error).message })
            return null
        }
    }

    const startNew = (): void => {
        stopStatusStream()
        stopAllStreaming()
        resetState()
        url.value = ''
    }

    const retryTask = async (): Promise<string | null> => {
        stopStatusStream()
        stopAllStreaming()
        resetState()
        url.value = lastUrl
        return submitUrl()
    }

    const copyContent = (): void => {
        if (!currentContent.value) return
        const toastStore = useToastStore()
        navigator.clipboard.writeText(currentContent.value).then(() => {
            toastStore.showToast('已复制到剪贴板', 'success')
        }).catch(() => {
            toastStore.showToast('复制失败，请手动选择复制', 'error')
        })
    }

    const generateSingleContent = (type: ContentType): void => {
        const wsId = wsCtx.workspaceId
        if (!wsId) return

        // 标记生成选项（zhihu 除外）
        if (type === 'outline') generateOptions.outline = true
        if (type === 'article') generateOptions.article = true
        if (type === 'podcast') generateOptions.podcast = true

        startSingleContentStream(wsId, type)
    }

    const loadWorkspaceById = async (id: string): Promise<boolean> => {
        if (wsCtx.workspaceId === id) return true

        stopStatusStream()
        stopAllStreaming()

        try {
            const data = await getWorkspace(id)
            sendWorkspace({ type: 'LOAD_WORKSPACE', status: data.status })
            sendWorkspace({
                type: 'UPDATE_RESOURCES',
                title: data.title,
                videoUrl: getResourceUrl(data.resources, 'video'),
                audioUrl: getResourceUrl(data.resources, 'audio'),
                transcript: getResourceContent(data.resources, 'transcript'),
                progressText: data.progress || undefined,
            })
            // 手动设置 workspaceId（LOAD_WORKSPACE 不设置 id）
            wsCtx.workspaceId = id

            // 加载已有内容
            const contentMap: Record<ContentType, string> = {
                outline: getResourceContent(data.resources, 'outline'),
                article: getResourceContent(data.resources, 'article'),
                podcast: getResourceContent(data.resources, 'podcast_script'),
                zhihu: getResourceContent(data.resources, 'zhihu'),
            }
            for (const type of CONTENT_TYPES) {
                if (contentMap[type]) {
                    contentCtxs[type].finalContent = contentMap[type]
                }
            }
            const podcastAudioResource = getResourceUrl(data.resources, 'podcast')
            if (podcastAudioResource) {
                contentCtxs.podcast.audioUrl = podcastAudioResource
            }

            if (data.error) {
                wsCtx.errorMessage = data.error
            }

            // 根据 status + resources 决定行为
            const hasContent = CONTENT_TYPES.some(t => !!contentMap[t])

            if (data.status === 'ready' && hasContent) {
                // resources 已有内容 → 直接显示，不重新生成
                handleTaskComplete()
            } else if (data.status === 'ready') {
                // 无内容 → 正常启动生成
                startGenerating(id)
            } else if (data.status !== 'failed') {
                // 还在处理中 → 监听 SSE
                startStatusStream(id)
            }

            return true
        } catch (error) {
            console.error('加载工作区失败:', error)
            return false
        }
    }

    // ==================== 导出 ====================

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
        isGenerating,
        hasGeneratedContent,
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
        generateSingleContent,
    }
})

export type TaskStore = ReturnType<typeof useTaskStore>
