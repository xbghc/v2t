<script setup>
import { ref, reactive, computed } from 'vue'
import { createUrlDownload, subscribeDownloadEvents } from './api/download'
import { createTranscript, subscribeTranscriptEvents, createOutline, createArticle, getOutline, getArticle, subscribeOutlineEvents, subscribeArticleEvents } from './api/transcript'
import { useSSE } from './composables/useSSE'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import InitialPage from './components/InitialPage.vue'
import ResultPage from './components/ResultPage.vue'

// 状态
const page = ref('initial')
const url = ref('')
const downloadOnly = ref(false)
const taskStatus = ref('pending')
const currentTab = ref('article')
const errorMessage = ref('无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。')

// 资源 ID
const downloadId = ref(null)
const videoId = ref(null)
const audioId = ref(null)
const transcriptId = ref(null)

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

let lastUrl = ''
let lastDownloadOnly = false

// SSE 订阅
const downloadSSE = useSSE({
    onStatus(data) {
        if (data.progress) {
            progress.text = data.progress
        }
        if (data.status === 'downloading') {
            taskStatus.value = 'downloading'
            progress.percent = 33
            progress.step = '步骤 1/3'
        }
        if (data.status === 'completed') {
            if (data.title) {
                progress.title = data.title
                result.title = data.title
            }
            if (data.video_id) {
                videoId.value = data.video_id
            }
            if (data.audio_id) {
                audioId.value = data.audio_id
            }
            result.has_video = true
            result.has_audio = true

            // 下载完成后自动开始转录（除非仅下载模式）
            if (!lastDownloadOnly) {
                startTranscript()
            } else {
                taskStatus.value = 'completed'
                progress.text = '下载完成'
                progress.percent = 100
                progress.step = '完成'
            }
        }
    },
    onDone() {
        // done 事件在 onStatus completed 之后处理
    },
    onError(message) {
        errorMessage.value = message
        taskStatus.value = 'failed'
    }
})

const transcriptSSE = useSSE({
    onStatus(data) {
        if (data.progress) {
            progress.text = data.progress
        }
        if (data.status === 'processing') {
            taskStatus.value = 'transcribing'
            progress.percent = 55
            progress.step = '步骤 2/3'
        }
        if (data.status === 'completed') {
            // 转录完成，开始生成大纲和文章
            startGeneration()
        }
    },
    onError(message) {
        errorMessage.value = message
        taskStatus.value = 'failed'
    }
})

const outlineSSE = useSSE({
    onStatus(data) {
        if (data.status === 'completed') {
            fetchOutline()
        }
    },
    onError(message) {
        console.warn('大纲生成失败:', message)
        // 大纲失败不影响整体流程
        checkGenerationComplete()
    }
})

const articleSSE = useSSE({
    onStatus(data) {
        if (data.status === 'completed') {
            fetchArticle()
        }
    },
    onError(message) {
        console.warn('文章生成失败:', message)
        // 文章失败不影响整体流程
        checkGenerationComplete()
    }
})

let outlineComplete = false
let articleComplete = false

// 当前内容（用于复制）
const currentContent = computed(() => {
    if (currentTab.value === 'article') return result.article || ''
    if (currentTab.value === 'outline') return result.outline || ''
    return result.transcript || ''
})

// 方法
const resetState = () => {
    taskStatus.value = 'pending'
    currentTab.value = 'article'
    errorMessage.value = '无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。'
    Object.assign(progress, { title: '', text: '准备中...', percent: 10, step: '步骤 1/3' })
    Object.assign(result, { title: '', has_video: false, has_audio: false, article: '', outline: '', transcript: '' })
    downloadId.value = null
    videoId.value = null
    audioId.value = null
    transcriptId.value = null
    outlineComplete = false
    articleComplete = false
}

const closeAllSSE = () => {
    downloadSSE.close()
    transcriptSSE.close()
    outlineSSE.close()
    articleSSE.close()
}

const startNew = () => {
    closeAllSSE()
    resetState()
    url.value = ''
    page.value = 'initial'
}

const retryTask = () => {
    closeAllSSE()
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
        // 创建下载任务
        const data = await createUrlDownload(url.value)
        downloadId.value = data.id

        if (data.created) {
            // 新建的下载任务，订阅 SSE
            progress.text = '开始下载...'
            downloadSSE.subscribe(subscribeDownloadEvents(data.id))
        } else {
            // 已存在的下载任务
            if (data.status === 'completed' && data.video_id && data.audio_id) {
                videoId.value = data.video_id
                audioId.value = data.audio_id

                // 获取视频信息
                try {
                    const { getVideo } = await import('./api/video')
                    const videoData = await getVideo(data.video_id)
                    result.title = videoData.title || ''
                    progress.title = videoData.title || ''
                    result.has_video = videoData.has_video
                    result.has_audio = true
                } catch (e) {
                    console.warn('获取视频信息失败:', e)
                }

                if (!lastDownloadOnly) {
                    // 直接开始转录
                    startTranscript()
                } else {
                    taskStatus.value = 'completed'
                    progress.text = '下载完成（已缓存）'
                    progress.percent = 100
                    progress.step = '完成'
                }
            } else if (data.status === 'downloading') {
                // 正在下载，订阅 SSE
                progress.text = '下载中...'
                downloadSSE.subscribe(subscribeDownloadEvents(data.id))
            } else {
                // pending 状态，订阅 SSE 等待
                progress.text = '开始下载...'
                downloadSSE.subscribe(subscribeDownloadEvents(data.id))
            }
        }
    } catch (error) {
        errorMessage.value = error.message
        taskStatus.value = 'failed'
    }
}

const startTranscript = async () => {
    if (!audioId.value) {
        errorMessage.value = '音频 ID 不存在'
        taskStatus.value = 'failed'
        return
    }

    try {
        taskStatus.value = 'transcribing'
        progress.text = '开始转录...'
        progress.percent = 55
        progress.step = '步骤 2/3'

        const data = await createTranscript(audioId.value)
        transcriptId.value = data.id

        // 订阅转录进度
        transcriptSSE.subscribe(subscribeTranscriptEvents(data.id))
    } catch (error) {
        errorMessage.value = error.message
        taskStatus.value = 'failed'
    }
}

const startGeneration = async () => {
    taskStatus.value = 'generating'
    progress.text = '正在生成内容...'
    progress.percent = 80
    progress.step = '步骤 3/3'

    outlineComplete = false
    articleComplete = false

    // 并行生成大纲和文章
    try {
        const outlineData = await createOutline(transcriptId.value)
        outlineSSE.subscribe(subscribeOutlineEvents(transcriptId.value))
    } catch (error) {
        console.warn('创建大纲失败:', error)
        outlineComplete = true
    }

    try {
        const articleData = await createArticle(transcriptId.value)
        articleSSE.subscribe(subscribeArticleEvents(transcriptId.value))
    } catch (error) {
        console.warn('创建文章失败:', error)
        articleComplete = true
    }

    // 如果两个都失败了，直接完成
    if (outlineComplete && articleComplete) {
        finishTask()
    }
}

const fetchOutline = async () => {
    try {
        const data = await getOutline(transcriptId.value)
        if (data.content) {
            result.outline = data.content
        }
    } catch (error) {
        console.warn('获取大纲失败:', error)
    }
    outlineComplete = true
    checkGenerationComplete()
}

const fetchArticle = async () => {
    try {
        const data = await getArticle(transcriptId.value)
        if (data.content) {
            result.article = data.content
        }
    } catch (error) {
        console.warn('获取文章失败:', error)
    }
    articleComplete = true
    checkGenerationComplete()
}

const checkGenerationComplete = () => {
    if (outlineComplete && articleComplete) {
        finishTask()
    }
}

const finishTask = async () => {
    // 获取转录内容
    try {
        const { getTranscript } = await import('./api/transcript')
        const data = await getTranscript(transcriptId.value)
        if (data.content) {
            result.transcript = data.content
        }
    } catch (error) {
        console.warn('获取转录失败:', error)
    }

    taskStatus.value = 'completed'
    progress.text = '处理完成'
    progress.percent = 100
    progress.step = '完成'

    // 自动切换到有内容的 tab
    currentTab.value = result.article ? 'article' : (result.outline ? 'outline' : 'transcript')
}

const copyContent = () => {
    if (!currentContent.value) return
    navigator.clipboard.writeText(currentContent.value).then(() => {
        alert('已复制到剪贴板')
    }).catch(() => {
        alert('复制失败，请手动选择复制')
    })
}
</script>

<template>
    <div class="relative flex min-h-screen w-full flex-col">
        <div class="layout-container flex h-full grow flex-col">
            <!-- Initial Page Layout -->
            <div v-if="page === 'initial'" class="flex flex-1 justify-center py-5 px-4 sm:px-8 md:px-20 lg:px-40">
                <div class="layout-content-container flex w-full flex-col max-w-content flex-1">
                    <AppHeader />
                    <InitialPage
                        v-model:url="url"
                        v-model:download-only="downloadOnly"
                        @submit="submitUrl"
                    />
                    <AppFooter />
                </div>
            </div>

            <!-- Result Page Layout -->
            <template v-else-if="page === 'result'">
                <AppHeader variant="result" :show-new-button="true" @new-task="startNew" />
                <ResultPage
                    :task-id="downloadId"
                    :task-status="taskStatus"
                    :error-message="errorMessage"
                    :progress="progress"
                    :result="result"
                    v-model:current-tab="currentTab"
                    @retry="retryTask"
                    @copy="copyContent"
                />
            </template>
        </div>
    </div>
</template>
