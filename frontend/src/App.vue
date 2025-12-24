<script setup>
import { ref, reactive, computed } from 'vue'
import { createTask, getTask } from './api/task'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import InitialPage from './components/InitialPage.vue'
import ResultPage from './components/ResultPage.vue'

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

// 当前内容（用于复制）
const currentContent = computed(() => {
    if (currentTab.value === 'article') return result.article || ''
    if (currentTab.value === 'outline') return result.outline || ''
    return result.transcript || ''
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
        const data = await createTask(url.value, lastDownloadOnly)
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
        const data = await getTask(taskId.value)

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
                    :task-id="taskId"
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
