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
import { createTaskMachine, createContentGenerators } from '@/stores/machines'
import type {
    WorkspaceResponse,
    WorkspaceResource,
    CurrentTab,
    CustomPrompts,
    GenerateOptions,
    InputMode,
    StreamPrompts,
    ContentType
} from '@/types'

export const useTaskStore = defineStore('task', () => {
    // ============ 状态机 ============
    const taskMachine = createTaskMachine()
    const generators = createContentGenerators()

    // ============ 输入状态 ============
    const inputMode: Ref<InputMode> = ref('url')
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

    // ============ 工作区资源 ============
    const currentTab: Ref<CurrentTab> = ref('article')
    const title: Ref<string> = ref('')
    const videoUrl: Ref<string | null> = ref(null)
    const audioUrl: Ref<string | null> = ref(null)
    const transcript: Ref<string> = ref('')

    // ============ 提示词状态 ============
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
    const PROMPTS_STORAGE_KEY = 'v2t_custom_prompts'

    // ============ 内部状态 ============
    let lastUrl: string = ''
    let statusStreamCleanup: (() => void) | null = null

    // ============ 计算属性 ============

    // 是否正在流式生成（任一内容类型）
    const isStreaming: ComputedRef<boolean> = computed(() =>
        generators.outline.isLoading.value ||
        generators.article.isLoading.value ||
        generators.podcast.isLoading.value ||
        generators.zhihu.isLoading.value
    )

    // 是否有播客音频
    const hasPodcastAudio: ComputedRef<boolean> = computed(() =>
        !!generators.podcast.audioUrl.value
    )

    // 当前内容（用于复制）
    const currentContent: ComputedRef<string> = computed(() => {
        switch (currentTab.value) {
        case 'article': return generators.article.displayContent.value
        case 'outline': return generators.outline.displayContent.value
        case 'podcast': return generators.podcast.displayContent.value
        case 'zhihu': return generators.zhihu.displayContent.value
        default: return transcript.value
        }
    })

    // ============ 兼容性别名 ============
    // 为保持向后兼容，暴露原有的状态名称
    const workspaceId = taskMachine.workspaceId
    const workspaceStatus = taskMachine.workspaceStatus
    const errorMessage = taskMachine.errorMessage
    const progressText = taskMachine.progressText
    const progressTitle = taskMachine.progressTitle

    // 流式状态
    const outlineStreaming = generators.outline.isStreaming
    const articleStreaming = generators.article.isStreaming
    const podcastStreaming = generators.podcast.isLoading  // 包含 streaming + synthesizing
    const podcastSynthesizing = generators.podcast.isSynthesizing
    const zhihuStreaming = generators.zhihu.isStreaming

    // 流式内容
    const streamingOutline = generators.outline.streamingContent
    const streamingArticle = generators.article.streamingContent
    const streamingPodcast = generators.podcast.streamingContent
    const streamingZhihu = generators.zhihu.streamingContent

    // 最终内容
    const outline = generators.outline.content
    const article = generators.article.content
    const podcastScript = generators.podcast.content
    const podcastAudioUrl = generators.podcast.audioUrl
    const podcastError = generators.podcast.error
    const zhihuArticle = generators.zhihu.content

    // 失败状态
    const outlineFailed = generators.outline.isFailed
    const articleFailed = generators.article.isFailed
    const podcastFailed = generators.podcast.isFailed
    const zhihuFailed = generators.zhihu.isFailed

    // 显示内容
    const displayOutline = generators.outline.displayContent
    const displayArticle = generators.article.displayContent
    const displayPodcast = generators.podcast.displayContent
    const displayZhihu = generators.zhihu.displayContent

    // ============ 辅助函数 ============

    const getResourceContent = (resources: WorkspaceResource[], name: string): string => {
        const resource = [...resources].reverse().find(r => r.name === name)
        return resource?.content || ''
    }

    const getResourceUrl = (resources: WorkspaceResource[], name: string): string | null => {
        const resource = [...resources].reverse().find(r => r.name === name)
        return resource?.download_url || null
    }

    // ============ 状态重置 ============

    const resetState = (): void => {
        taskMachine.reset()
        generators.outline.reset()
        generators.article.reset()
        generators.podcast.reset()
        generators.zhihu.reset()

        currentTab.value = 'article'
        title.value = ''
        videoUrl.value = null
        audioUrl.value = null
        transcript.value = ''
    }

    // ============ 提示词管理 ============

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

    // ============ 流管理 ============

    const stopStatusStream = (): void => {
        if (statusStreamCleanup) {
            statusStreamCleanup()
            statusStreamCleanup = null
        }
    }

    const stopAllStreaming = (): void => {
        // 清理所有内容生成器的流
        for (const generator of Object.values(generators)) {
            if (generator.cleanup.value) {
                generator.cleanup.value()
                generator.cleanup.value = null
            }
        }
        // 重置状态（但不清空内容）
        generators.outline.state.value = generators.outline.content.value ? 'completed' : 'idle'
        generators.article.state.value = generators.article.content.value ? 'completed' : 'idle'
        generators.podcast.state.value = generators.podcast.content.value ? 'completed' : 'idle'
        generators.zhihu.state.value = generators.zhihu.content.value ? 'completed' : 'idle'
    }

    // ============ 生成完成检查 ============

    const checkAllGenerationDone = (): void => {
        const activeGenerators = [
            generateOptions.outline && generators.outline,
            generateOptions.article && generators.article,
            generateOptions.podcast && generators.podcast
        ].filter(Boolean)

        // 检查所有激活的生成器是否都完成或失败
        const allDone = activeGenerators.every(g =>
            g && (g.isCompleted.value || g.isFailed.value)
        )

        if (allDone) {
            taskMachine.send({ type: 'GENERATION_COMPLETE' })
            handleTaskComplete()
        }
    }

    // ============ 内容生成 ============

    const startGenerating = (wsId: string): void => {
        taskMachine.send({ type: 'READY_TO_GENERATE' })

        if (generateOptions.outline) {
            startOutlineGeneration(wsId)
        }

        if (generateOptions.article) {
            startArticleGeneration(wsId)
        }

        if (generateOptions.podcast) {
            startPodcastGeneration(wsId)
        }

        // 如果没有选择任何生成选项，直接完成
        if (!generateOptions.outline && !generateOptions.article && !generateOptions.podcast) {
            taskMachine.send({ type: 'GENERATION_COMPLETE' })
            handleTaskComplete()
        }
    }

    const startOutlineGeneration = (wsId: string): void => {
        generators.outline.send({ type: 'START' })
        const outlinePrompts: StreamPrompts = {
            systemPrompt: prompts.outlineSystem,
            userPrompt: prompts.outlineUser
        }
        generators.outline.cleanup.value = streamOutline(
            wsId,
            outlinePrompts,
            () => {},
            (chunk) => generators.outline.send({ type: 'CHUNK', content: chunk }),
            () => {
                generators.outline.send({ type: 'COMPLETE' })
                checkAllGenerationDone()
            },
            (err) => {
                console.error('大纲生成失败:', err)
                generators.outline.send({ type: 'ERROR', error: err })
                checkAllGenerationDone()
            }
        )
    }

    const startArticleGeneration = (wsId: string): void => {
        generators.article.send({ type: 'START' })
        const articlePrompts: StreamPrompts = {
            systemPrompt: prompts.articleSystem,
            userPrompt: prompts.articleUser
        }
        generators.article.cleanup.value = streamArticle(
            wsId,
            articlePrompts,
            () => {},
            (chunk) => generators.article.send({ type: 'CHUNK', content: chunk }),
            () => {
                generators.article.send({ type: 'COMPLETE' })
                checkAllGenerationDone()
            },
            (err) => {
                console.error('文章生成失败:', err)
                generators.article.send({ type: 'ERROR', error: err })
                checkAllGenerationDone()
            }
        )
    }

    const startPodcastGeneration = (wsId: string): void => {
        generators.podcast.send({ type: 'START' })
        const podcastPrompts: StreamPrompts = {
            systemPrompt: prompts.podcastSystem,
            userPrompt: prompts.podcastUser
        }
        generators.podcast.cleanup.value = streamPodcast(
            wsId,
            podcastPrompts,
            () => {},
            (chunk) => generators.podcast.send({ type: 'CHUNK', content: chunk }),
            () => {},
            () => generators.podcast.send({ type: 'SYNTHESIZE_START' }),
            (hasAudio, audioResourceId, audioErr) => {
                let audioUrl: string | undefined
                if (hasAudio && audioResourceId && workspaceId.value) {
                    audioUrl = `/api/workspaces/${workspaceId.value}/resources/${audioResourceId}`
                }
                generators.podcast.send({
                    type: 'COMPLETE',
                    audioUrl,
                    audioError: audioErr
                })
                checkAllGenerationDone()
            },
            (err) => {
                console.error('播客生成失败:', err)
                generators.podcast.send({ type: 'ERROR', error: err })
                checkAllGenerationDone()
            }
        )
    }

    const startZhihuGeneration = (wsId: string): void => {
        generators.zhihu.send({ type: 'START' })
        const zhihuPrompts: StreamPrompts = {
            systemPrompt: prompts.zhihuSystem,
            userPrompt: prompts.zhihuUser
        }
        generators.zhihu.cleanup.value = streamZhihuArticle(
            wsId,
            zhihuPrompts,
            () => {},
            (chunk) => generators.zhihu.send({ type: 'CHUNK', content: chunk }),
            () => generators.zhihu.send({ type: 'COMPLETE' }),
            (err) => {
                console.error('知乎文章生成失败:', err)
                generators.zhihu.send({ type: 'ERROR', error: err })
            }
        )
    }

    // ============ 工作区状态更新 ============

    const updateWorkspaceState = (data: WorkspaceResponse): void => {
        title.value = data.title

        // 从资源列表获取内容
        const resources = data.resources
        videoUrl.value = getResourceUrl(resources, 'video')
        audioUrl.value = getResourceUrl(resources, 'audio')
        transcript.value = getResourceContent(resources, 'transcript')

        // 如果已有生成内容，从资源中获取
        if (!generators.outline.content.value) {
            const content = getResourceContent(resources, 'outline')
            if (content) {
                generators.outline.content.value = content
                generators.outline.state.value = 'completed'
            }
        }
        if (!generators.article.content.value) {
            const content = getResourceContent(resources, 'article')
            if (content) {
                generators.article.content.value = content
                generators.article.state.value = 'completed'
            }
        }
        if (!generators.podcast.content.value) {
            const content = getResourceContent(resources, 'podcast_script')
            if (content) {
                generators.podcast.content.value = content
                generators.podcast.state.value = 'completed'
            }
        }
        if (!generators.zhihu.content.value) {
            const content = getResourceContent(resources, 'zhihu')
            if (content) {
                generators.zhihu.content.value = content
                generators.zhihu.state.value = 'completed'
            }
        }

        // 获取播客音频 URL
        const podcastAudio = getResourceUrl(resources, 'podcast')
        if (podcastAudio) {
            generators.podcast.audioUrl.value = podcastAudio
        }
    }

    const handleStatusStreamUpdate = (data: WorkspaceResponse): void => {
        taskMachine.send({
            type: 'STATUS_UPDATE',
            status: data.status,
            data
        })
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

    const startStatusStream = (id: string): void => {
        taskMachine.workspaceId.value = id
        stopStatusStream()
        statusStreamCleanup = streamWorkspaceStatus(
            id,
            handleStatusStreamUpdate,
            (err) => {
                console.error('状态流错误:', err)
            }
        )
    }

    // ============ 任务完成处理 ============

    const handleTaskComplete = (): void => {
        if (generators.article.content.value) {
            currentTab.value = 'article'
        } else if (generators.zhihu.content.value) {
            currentTab.value = 'zhihu'
        } else if (generators.outline.content.value) {
            currentTab.value = 'outline'
        } else if (generators.podcast.content.value) {
            currentTab.value = 'podcast'
        } else {
            currentTab.value = 'transcript'
        }
    }

    // ============ 公共方法 ============

    const submitUrl = async (): Promise<string | null> => {
        const toastStore = useToastStore()
        if (!url.value.trim()) {
            toastStore.showToast('请输入视频链接', 'warning')
            return null
        }

        lastUrl = url.value
        savePromptsToStorage()
        resetState()
        taskMachine.send({ type: 'SUBMIT', url: url.value })

        try {
            const data = await createWorkspace(url.value)
            taskMachine.send({ type: 'SUBMIT_SUCCESS', workspaceId: data.workspace_id })
            startStatusStream(data.workspace_id)
            return data.workspace_id
        } catch (error) {
            taskMachine.send({ type: 'SUBMIT_ERROR', error: (error as Error).message })
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
        if (!workspaceId.value) return
        const wsId = workspaceId.value
        const generator = generators[type]

        // 只有在空闲、完成或失败状态才能开始新的生成
        if (!generator.isIdle.value && !generator.isCompleted.value && !generator.isFailed.value) {
            return
        }

        // 更新生成选项
        if (type !== 'zhihu') {
            generateOptions[type] = true
        }

        switch (type) {
        case 'outline':
            startOutlineGeneration(wsId)
            break
        case 'article':
            startArticleGeneration(wsId)
            break
        case 'podcast':
            startPodcastGeneration(wsId)
            break
        case 'zhihu':
            startZhihuGeneration(wsId)
            break
        }
    }

    const loadWorkspaceById = async (id: string): Promise<boolean> => {
        if (workspaceId.value === id) {
            return true
        }

        stopStatusStream()
        stopAllStreaming()

        try {
            const data = await getWorkspace(id)
            taskMachine.workspaceId.value = id
            taskMachine.send({
                type: 'STATUS_UPDATE',
                status: data.status,
                data
            })
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
        // 状态机（供调试使用）
        taskMachine,
        generators,

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
