<script setup lang="ts">
import { computed, onMounted } from 'vue'
import type { ComputedRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { marked } from 'marked'
import { useTaskStore } from '@/stores/task'
import MediaDownload from './MediaDownload.vue'
import PodcastPlayer from './PodcastPlayer.vue'
import ContentTabs from './ContentTabs.vue'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()

// 重试并导航
const handleRetry = async () => {
    const taskId = await taskStore.retryTask()
    if (taskId) {
        router.push({ name: 'task', params: { id: taskId } })
    }
}

// 从 store 获取响应式状态
const {
    taskId,
    taskStatus,
    errorMessage,
    progressText,
    result,
    currentContent,
    isStreaming,
    podcastStreaming,
    podcastSynthesizing,
    currentTab
} = storeToRefs(taskStore)

// 从 URL 参数加载任务
onMounted(async () => {
    const urlTaskId = route.params.id as string
    if (urlTaskId && urlTaskId !== 'error') {
        // 如果 store 中没有此任务，从服务器加载
        if (!taskId.value || taskId.value !== urlTaskId) {
            const loaded = await taskStore.loadTaskById(urlTaskId)
            if (!loaded) {
                // 任务不存在或加载失败，返回首页
                // 添加错误提示
                router.push({ name: 'home' })
            }
        }
    }
})

const isProcessing: ComputedRef<boolean> = computed(() => {
    return taskStatus.value !== 'completed' && taskStatus.value !== 'failed'
})

// 是否正在流式生成（有流式内容或正在streaming）
const isStreamingContent: ComputedRef<boolean> = computed(() => {
    return isStreaming.value && !!currentContent.value
})

const isFailed: ComputedRef<boolean> = computed(() => {
    return taskStatus.value === 'failed'
})

const hasTextContent: ComputedRef<boolean> = computed(() => {
    return !!(result.value.transcript || result.value.outline || result.value.article || result.value.podcast_script)
})

const showPodcast: ComputedRef<boolean> = computed(() => {
    return !!(result.value.podcast_script || result.value.has_podcast_audio)
})

const isContentLoading: ComputedRef<boolean> = computed(() => {
    if (!isProcessing.value && !isFailed.value) {
        return false
    }
    // 如果有流式内容正在显示，不显示加载状态
    if (currentContent.value && isStreaming.value) {
        return false
    }
    if (currentTab.value === 'transcript') {
        return !result.value.transcript
    }
    if (currentTab.value === 'outline') {
        return !result.value.outline && !currentContent.value && isProcessing.value
    }
    if (currentTab.value === 'article') {
        return !result.value.article && !currentContent.value && isProcessing.value
    }
    if (currentTab.value === 'podcast') {
        return !result.value.podcast_script && isProcessing.value
    }
    return false
})

const contentLoadingText: ComputedRef<string> = computed(() => {
    if (currentTab.value === 'transcript') {
        if (taskStatus.value === 'downloading') return '正在下载视频，转录内容稍后显示...'
        if (taskStatus.value === 'transcribing') return '正在转录音频...'
        return '准备中...'
    }
    if (currentTab.value === 'outline' || currentTab.value === 'article') {
        if (taskStatus.value === 'downloading') return '正在下载视频...'
        if (taskStatus.value === 'transcribing') return '正在转录音频...'
        if (taskStatus.value === 'ready') return '准备生成内容...'
        return '准备中...'
    }
    if (currentTab.value === 'podcast') {
        if (taskStatus.value === 'downloading') return '正在下载视频...'
        if (taskStatus.value === 'transcribing') return '正在转录音频...'
        if (taskStatus.value === 'ready') return '准备生成内容...'
        if (podcastSynthesizing.value) return '正在合成播客音频...'
        if (podcastStreaming.value) return '正在生成播客脚本...'
        return '准备中...'
    }
    return '加载中...'
})

const renderedContent: ComputedRef<string> = computed(() => {
    if (!currentContent.value) {
        if (isFailed.value) return '<p class="text-gray-500">(处理失败，无法生成内容)</p>'
        if (!isProcessing.value) {
            if (currentTab.value === 'article') return '<p class="text-gray-500">(详细内容生成失败)</p>'
            if (currentTab.value === 'outline') return '<p class="text-gray-500">(大纲生成失败)</p>'
            if (currentTab.value === 'podcast') return '<p class="text-gray-500">(播客脚本生成失败)</p>'
            return '<p class="text-gray-500">(无转录内容)</p>'
        }
        return ''
    }
    return marked.parse(currentContent.value) as string
})

const statusTitle: ComputedRef<string> = computed(() => {
    if (isFailed.value) return '转换失败'
    if (isProcessing.value) return '正在处理'
    return '转换完成'
})

const statusDescription: ComputedRef<string> = computed(() => {
    if (isFailed.value) return errorMessage.value
    if (isStreamingContent.value) return '内容正在实时生成中...'
    if (isProcessing.value) return '请勿关闭页面，内容将逐步显示'
    return '查看生成的内容，复制或下载原始媒体文件'
})

// 资源 URL 需要加上 BASE_URL 前缀
const BASE_URL = import.meta.env.BASE_URL
const videoDownloadUrl: ComputedRef<string> = computed(() =>
    result.value.video_url ? `${BASE_URL}${result.value.video_url.replace(/^\//, '')}` : ''
)
const audioDownloadUrl: ComputedRef<string> = computed(() =>
    result.value.audio_url ? `${BASE_URL}${result.value.audio_url.replace(/^\//, '')}` : ''
)
const podcastDownloadUrl: ComputedRef<string> = computed(() =>
    taskId.value ? `${BASE_URL}api/task/${taskId.value}/podcast` : ''
)
</script>

<template>
    <main class="px-6 sm:px-10 lg:px-20 flex flex-1 justify-center py-5 sm:py-8 md:py-10">
        <div class="layout-content-container flex flex-col w-full max-w-7xl flex-1">
            <!-- PageHeading -->
            <div class="flex flex-wrap justify-between gap-3 p-4">
                <div class="flex min-w-72 flex-col gap-2">
                    <p class="text-gray-900 dark:text-white text-4xl font-black leading-tight tracking-tight-lg">
                        {{ statusTitle }}
                    </p>
                    <p class="text-gray-500 dark:text-dark-text-muted text-base font-normal leading-normal">
                        {{ statusDescription }}
                    </p>
                </div>
                <div
                    v-if="isFailed"
                    class="flex items-center"
                >
                    <button
                        class="flex min-w-btn cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold leading-normal tracking-wide-sm hover:bg-primary/90 transition-colors"
                        @click="handleRetry"
                    >
                        <span class="truncate">重新尝试</span>
                    </button>
                </div>
            </div>

            <!-- Progress Text -->
            <div
                v-if="isProcessing"
                class="px-4 pb-4"
            >
                <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-lg p-4">
                    <div class="flex items-center gap-3">
                        <div class="animate-spin rounded-full h-5 w-5 border-2 border-primary border-t-transparent" />
                        <span class="text-sm text-gray-600 dark:text-gray-300">{{ progressText }}</span>
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 p-4 mt-4">
                <!-- Left Column: Video Info -->
                <aside class="lg:col-span-1 flex flex-col gap-6">
                    <div class="flex flex-col gap-4">
                        <div class="flex flex-col gap-1">
                            <p class="text-gray-900 dark:text-white text-lg font-bold leading-tight">
                                {{ result.title || '视频标题' }}
                            </p>
                        </div>
                        <div class="flex flex-col sm:flex-row lg:flex-col gap-3">
                            <MediaDownload
                                type="video"
                                :available="!!result.video_url"
                                :is-processing="isProcessing"
                                :download-url="videoDownloadUrl"
                            />
                            <MediaDownload
                                type="audio"
                                :available="!!result.audio_url"
                                :is-processing="isProcessing"
                                :download-url="audioDownloadUrl"
                            />
                            <PodcastPlayer
                                v-if="showPodcast || podcastStreaming || podcastSynthesizing"
                                :src="podcastDownloadUrl"
                                :available="result.has_podcast_audio"
                                :is-processing="podcastStreaming || podcastSynthesizing"
                                :error="result.podcast_error"
                            />
                        </div>
                    </div>
                </aside>

                <!-- Right Column: Content -->
                <ContentTabs
                    v-if="hasTextContent || isProcessing"
                    v-model:current-tab="currentTab"
                    :is-loading="isContentLoading"
                    :loading-text="contentLoadingText"
                    :rendered-content="renderedContent"
                    :show-podcast="showPodcast"
                    @copy="taskStore.copyContent()"
                />

                <!-- 仅下载模式提示 -->
                <div
                    v-else-if="!isFailed"
                    class="lg:col-span-2 flex flex-col items-center justify-center bg-white dark:bg-dark-bg rounded-xl border border-gray-200 dark:border-dark-border p-12"
                >
                    <span class="material-symbols-outlined text-5xl text-gray-400 dark:text-gray-600 mb-4">download_done</span>
                    <p class="text-gray-600 dark:text-gray-400 text-center">
                        仅下载模式，无文字内容
                    </p>
                    <p class="text-gray-500 dark:text-gray-500 text-sm text-center mt-2">
                        请使用左侧按钮下载视频或音频文件
                    </p>
                </div>
            </div>
        </div>
    </main>
</template>
