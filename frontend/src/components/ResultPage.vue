<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { ComputedRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { marked } from 'marked'
import { useTaskStore } from '@/stores/task'
import { useToastStore } from '@/stores/toast'
import type { SideNavItem, SideNavKey } from '@/types'
import SideNavigation from './SideNavigation.vue'
import ContentSection from './ContentSection.vue'
import VideoSection from './VideoSection.vue'
import AudioSection from './AudioSection.vue'
import SubtitleSection from './SubtitleSection.vue'
import PodcastPlayer from './PodcastPlayer.vue'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const toastStore = useToastStore()

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
    progressText,
    videoResult,
    // 生成内容
    outline,
    article,
    podcastScript,
    hasPodcastAudio,
    podcastError,
    zhihuArticle,
    generateOptions,
    podcastStreaming,
    podcastSynthesizing,
    outlineStreaming,
    articleStreaming,
    zhihuStreaming,
    displayOutline,
    displayArticle,
    displayPodcast,
    displayZhihu,
    // 失败状态
    outlineFailed,
    articleFailed,
    podcastFailed,
    zhihuFailed
} = storeToRefs(taskStore)

// 聚焦模式状态
const focusedSection = ref<SideNavKey | null>(null)

// 从 URL 参数加载任务
onMounted(async () => {
    const urlTaskId = route.params.id as string
    if (urlTaskId && urlTaskId !== 'error') {
        if (!taskId.value || taskId.value !== urlTaskId) {
            const loaded = await taskStore.loadTaskById(urlTaskId)
            if (!loaded) {
                router.push({ name: 'home' })
            }
        }
    }
})

// 计算属性
const isProcessing: ComputedRef<boolean> = computed(() => {
    return taskStatus.value !== 'completed' && taskStatus.value !== 'failed'
})

const isFailed: ComputedRef<boolean> = computed(() => {
    return taskStatus.value === 'failed'
})

const statusTitle: ComputedRef<string> = computed(() => {
    if (isFailed.value) return '转换失败'
    if (isProcessing.value) return '正在处理'
    return '转换完成'
})

// 资源 URL
const BASE_URL = import.meta.env.BASE_URL
const videoDownloadUrl: ComputedRef<string> = computed(() =>
    videoResult.value.video_url ? `${BASE_URL}${videoResult.value.video_url.replace(/^\//, '')}` : ''
)
const audioDownloadUrl: ComputedRef<string> = computed(() =>
    videoResult.value.audio_url ? `${BASE_URL}${videoResult.value.audio_url.replace(/^\//, '')}` : ''
)
const podcastDownloadUrl: ComputedRef<string> = computed(() =>
    taskId.value ? `${BASE_URL}api/task/${taskId.value}/podcast` : ''
)

// 内容渲染
const renderedArticle: ComputedRef<string> = computed(() => {
    if (!displayArticle.value) return ''
    return marked.parse(displayArticle.value) as string
})

const renderedOutline: ComputedRef<string> = computed(() => {
    if (!displayOutline.value) return ''
    return marked.parse(displayOutline.value) as string
})

const renderedPodcastScript: ComputedRef<string> = computed(() => {
    if (!displayPodcast.value) return ''
    return marked.parse(displayPodcast.value) as string
})

const renderedZhihuArticle: ComputedRef<string> = computed(() => {
    if (!displayZhihu.value) return ''
    return marked.parse(displayZhihu.value) as string
})

// 导航项计算
const navItems = computed<SideNavItem[]>(() => {
    const items: SideNavItem[] = []

    // 播客
    if (generateOptions.value.podcast || podcastScript.value || hasPodcastAudio.value) {
        items.push({
            key: 'podcast',
            label: '播客',
            icon: 'podcasts',
            hasContent: !!podcastScript.value || hasPodcastAudio.value,
            isLoading: podcastStreaming.value || podcastSynthesizing.value
        })
    }

    // 文章
    if (generateOptions.value.article || article.value) {
        items.push({
            key: 'article',
            label: '文章',
            icon: 'article',
            hasContent: !!article.value || !!displayArticle.value,
            isLoading: articleStreaming.value
        })
    }

    // 知乎（只有已有内容或正在生成时才显示）
    if (zhihuArticle.value || zhihuStreaming.value) {
        items.push({
            key: 'zhihu',
            label: '知乎',
            icon: 'edit_document',
            hasContent: !!zhihuArticle.value || !!displayZhihu.value,
            isLoading: zhihuStreaming.value
        })
    }

    // 大纲
    if (generateOptions.value.outline || outline.value) {
        items.push({
            key: 'outline',
            label: '大纲',
            icon: 'format_list_bulleted',
            hasContent: !!outline.value || !!displayOutline.value,
            isLoading: outlineStreaming.value
        })
    }

    // 视频（始终显示）
    items.push({
        key: 'video',
        label: '视频',
        icon: 'videocam',
        hasContent: !!videoResult.value.video_url,
        isLoading: taskStatus.value === 'downloading'
    })

    // 音频（始终显示）
    items.push({
        key: 'audio',
        label: '音频',
        icon: 'music_note',
        hasContent: !!videoResult.value.audio_url,
        isLoading: taskStatus.value === 'downloading'
    })

    // 字幕（始终显示）
    items.push({
        key: 'subtitle',
        label: '字幕',
        icon: 'subtitles',
        hasContent: !!videoResult.value.transcript,
        isLoading: taskStatus.value === 'transcribing'
    })

    return items
})

// 可生成项
const disabledItems = computed<SideNavItem[]>(() => {
    const items: SideNavItem[] = []

    // 只有当任务状态为 ready 或 completed 时，才显示可生成项
    if (taskStatus.value !== 'ready' && taskStatus.value !== 'completed') {
        return items
    }

    // 播客（用户未选择且没有内容）
    if (!generateOptions.value.podcast && !podcastScript.value && !hasPodcastAudio.value) {
        items.push({
            key: 'podcast',
            label: '播客',
            icon: 'podcasts',
            hasContent: false,
            isLoading: false
        })
    }

    // 文章
    if (!generateOptions.value.article && !article.value) {
        items.push({
            key: 'article',
            label: '文章',
            icon: 'article',
            hasContent: false,
            isLoading: false
        })
    }

    // 知乎
    if (!zhihuArticle.value && !zhihuStreaming.value) {
        items.push({
            key: 'zhihu',
            label: '知乎',
            icon: 'edit_document',
            hasContent: false,
            isLoading: false
        })
    }

    // 大纲
    if (!generateOptions.value.outline && !outline.value) {
        items.push({
            key: 'outline',
            label: '大纲',
            icon: 'format_list_bulleted',
            hasContent: false,
            isLoading: false
        })
    }

    return items
})

// 切换聚焦模式
const toggleFocus = (key: SideNavKey) => {
    focusedSection.value = focusedSection.value === key ? null : key
}

// 判断区块是否可见
const isSectionVisible = (key: SideNavKey): boolean => {
    return focusedSection.value === null || focusedSection.value === key
}

// 滚动到指定区块
const scrollToSection = (key: SideNavKey) => {
    const element = document.getElementById(`section-${key}`)
    element?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// 生成单个内容
const handleGenerateContent = (key: SideNavKey) => {
    if (key === 'podcast' || key === 'article' || key === 'outline' || key === 'zhihu') {
        taskStore.generateSingleContent(key)
        const labels: Record<string, string> = {
            podcast: '播客',
            article: '文章',
            outline: '大纲',
            zhihu: '知乎文章'
        }
        toastStore.showToast(`正在生成${labels[key]}...`, 'info')
    }
}

// 复制内容
const copyContent = (content: string) => {
    if (!content) return
    navigator.clipboard.writeText(content).then(() => {
        toastStore.showToast('已复制到剪贴板', 'success')
    }).catch(() => {
        toastStore.showToast('复制失败，请手动选择复制', 'error')
    })
}

// 是否显示播客区块（只有在任务准备好或已有内容时才显示）
const showPodcast = computed(() => {
    // 已有内容或正在生成
    if (podcastScript.value || hasPodcastAudio.value || podcastStreaming.value || podcastSynthesizing.value) return true
    // 用户选择了生成，且任务已准备好开始生成
    if (generateOptions.value.podcast && (taskStatus.value === 'ready' || taskStatus.value === 'completed')) return true
    return false
})

// 是否显示文章区块（只有在任务准备好或已有内容时才显示）
const showArticle = computed(() => {
    // 已有内容或正在生成
    if (article.value || articleStreaming.value) return true
    // 用户选择了生成，且任务已准备好开始生成
    if (generateOptions.value.article && (taskStatus.value === 'ready' || taskStatus.value === 'completed')) return true
    return false
})

// 是否显示大纲区块（只有在任务准备好或已有内容时才显示）
const showOutline = computed(() => {
    // 已有内容或正在生成
    if (outline.value || outlineStreaming.value) return true
    // 用户选择了生成，且任务已准备好开始生成
    if (generateOptions.value.outline && (taskStatus.value === 'ready' || taskStatus.value === 'completed')) return true
    return false
})

// 是否显示知乎区块
const showZhihu = computed(() => {
    // 已有内容或正在生成
    if (zhihuArticle.value || zhihuStreaming.value) return true
    return false
})

// 加载状态文本
const getLoadingText = (key: SideNavKey): string => {
    if (taskStatus.value === 'downloading') return '正在下载视频...'
    if (taskStatus.value === 'transcribing') return '正在转录音频...'
    if (key === 'podcast' && podcastSynthesizing.value) return '正在合成播客音频...'
    if (key === 'podcast' && podcastStreaming.value) return '正在生成播客脚本...'
    if (key === 'article' && articleStreaming.value) return '正在生成文章...'
    if (key === 'outline' && outlineStreaming.value) return '正在生成大纲...'
    if (key === 'zhihu' && zhihuStreaming.value) return '正在生成知乎文章...'
    return '加载中...'
}
</script>

<template>
    <main class="flex flex-1 min-h-0">
        <!-- 侧边导航 -->
        <SideNavigation
            :items="navItems"
            :disabled-items="disabledItems"
            :focused-item="focusedSection"
            @scroll-to="scrollToSection"
            @toggle-focus="toggleFocus"
            @generate="handleGenerateContent"
        />

        <!-- 主内容区 -->
        <div class="flex-1 overflow-y-auto lg:ml-0">
            <div class="max-w-5xl mx-auto px-6 py-8">
                <!-- 页面头部 -->
                <div class="mb-8">
                    <div class="flex flex-wrap items-center justify-between gap-4">
                        <div>
                            <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">
                                {{ statusTitle }}
                            </h1>
                            <p
                                v-if="videoResult.title"
                                class="text-lg text-gray-600 dark:text-gray-400"
                            >
                                {{ videoResult.title }}
                            </p>
                        </div>

                        <!-- 重试按钮 -->
                        <button
                            v-if="isFailed"
                            class="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                            @click="handleRetry"
                        >
                            <span class="material-symbols-outlined">refresh</span>
                            <span>重新尝试</span>
                        </button>
                    </div>

                    <!-- 进度指示器 -->
                    <div
                        v-if="isProcessing"
                        class="mt-4 p-4 bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-lg"
                    >
                        <div class="flex items-center gap-3">
                            <div class="animate-spin rounded-full h-5 w-5 border-2 border-primary border-t-transparent" />
                            <span class="text-sm text-gray-600 dark:text-gray-300">{{ progressText }}</span>
                        </div>
                    </div>
                </div>

                <!-- 内容区块列表 -->
                <div class="space-y-6">
                    <!-- 播客区块 -->
                    <ContentSection
                        v-if="showPodcast"
                        id="podcast"
                        title="播客"
                        icon="podcasts"
                        :is-visible="isSectionVisible('podcast')"
                        :is-loading="podcastStreaming || podcastSynthesizing"
                        :loading-text="getLoadingText('podcast')"
                    >
                        <template #actions>
                            <button
                                v-if="podcastScript"
                                class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-border rounded-lg transition-colors"
                                @click="copyContent(podcastScript)"
                            >
                                <span class="material-symbols-outlined text-lg">content_copy</span>
                                <span>复制脚本</span>
                            </button>
                        </template>

                        <!-- 播客播放器 -->
                        <PodcastPlayer
                            :src="podcastDownloadUrl"
                            :available="hasPodcastAudio"
                            :is-processing="podcastSynthesizing"
                            :error="podcastError"
                        />

                        <!-- 播客脚本 -->
                        <div
                            v-if="displayPodcast"
                            class="mt-6 prose prose-sm dark:prose-invert max-w-none"
                            v-html="renderedPodcastScript"
                        />
                        <!-- 生成失败：显示失败提示和重试按钮 -->
                        <div
                            v-else-if="podcastFailed && !hasPodcastAudio"
                            class="flex flex-col items-center justify-center py-12 gap-4"
                        >
                            <span class="material-symbols-outlined text-4xl text-red-400">error_outline</span>
                            <p class="text-gray-500 dark:text-gray-400">
                                播客生成失败
                            </p>
                            <button
                                class="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                                @click="handleGenerateContent('podcast')"
                            >
                                <span class="material-symbols-outlined text-lg">refresh</span>
                                <span>重新生成</span>
                            </button>
                        </div>
                    </ContentSection>

                    <!-- 文章区块 -->
                    <ContentSection
                        v-if="showArticle"
                        id="article"
                        title="文章"
                        icon="article"
                        :is-visible="isSectionVisible('article')"
                        :is-loading="articleStreaming && !displayArticle"
                        :loading-text="getLoadingText('article')"
                    >
                        <template #actions>
                            <button
                                v-if="article || displayArticle"
                                class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-border rounded-lg transition-colors"
                                @click="copyContent(article || displayArticle)"
                            >
                                <span class="material-symbols-outlined text-lg">content_copy</span>
                                <span>复制</span>
                            </button>
                        </template>

                        <div
                            v-if="displayArticle"
                            class="prose prose-sm md:prose-base dark:prose-invert max-w-none"
                            v-html="renderedArticle"
                        />
                        <!-- 生成失败：显示失败提示和重试按钮 -->
                        <div
                            v-else-if="articleFailed"
                            class="flex flex-col items-center justify-center py-12 gap-4"
                        >
                            <span class="material-symbols-outlined text-4xl text-red-400">error_outline</span>
                            <p class="text-gray-500 dark:text-gray-400">
                                文章生成失败
                            </p>
                            <button
                                class="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                                @click="handleGenerateContent('article')"
                            >
                                <span class="material-symbols-outlined text-lg">refresh</span>
                                <span>重新生成</span>
                            </button>
                        </div>
                    </ContentSection>

                    <!-- 大纲区块 -->
                    <ContentSection
                        v-if="showOutline"
                        id="outline"
                        title="大纲"
                        icon="format_list_bulleted"
                        :is-visible="isSectionVisible('outline')"
                        :is-loading="outlineStreaming && !displayOutline"
                        :loading-text="getLoadingText('outline')"
                    >
                        <template #actions>
                            <button
                                v-if="outline || displayOutline"
                                class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-border rounded-lg transition-colors"
                                @click="copyContent(outline || displayOutline)"
                            >
                                <span class="material-symbols-outlined text-lg">content_copy</span>
                                <span>复制</span>
                            </button>
                        </template>

                        <div
                            v-if="displayOutline"
                            class="prose prose-sm md:prose-base dark:prose-invert max-w-none"
                            v-html="renderedOutline"
                        />
                        <!-- 生成失败：显示失败提示和重试按钮 -->
                        <div
                            v-else-if="outlineFailed"
                            class="flex flex-col items-center justify-center py-12 gap-4"
                        >
                            <span class="material-symbols-outlined text-4xl text-red-400">error_outline</span>
                            <p class="text-gray-500 dark:text-gray-400">
                                大纲生成失败
                            </p>
                            <button
                                class="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                                @click="handleGenerateContent('outline')"
                            >
                                <span class="material-symbols-outlined text-lg">refresh</span>
                                <span>重新生成</span>
                            </button>
                        </div>
                    </ContentSection>

                    <!-- 知乎区块 -->
                    <ContentSection
                        v-if="showZhihu"
                        id="zhihu"
                        title="知乎文章"
                        icon="edit_document"
                        :is-visible="isSectionVisible('zhihu')"
                        :is-loading="zhihuStreaming && !displayZhihu"
                        :loading-text="getLoadingText('zhihu')"
                    >
                        <template #actions>
                            <button
                                v-if="zhihuArticle || displayZhihu"
                                class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-border rounded-lg transition-colors"
                                @click="copyContent(zhihuArticle || displayZhihu)"
                            >
                                <span class="material-symbols-outlined text-lg">content_copy</span>
                                <span>复制</span>
                            </button>
                        </template>

                        <div
                            v-if="displayZhihu"
                            class="prose prose-sm md:prose-base dark:prose-invert max-w-none"
                            v-html="renderedZhihuArticle"
                        />
                        <!-- 生成失败：显示失败提示和重试按钮 -->
                        <div
                            v-else-if="zhihuFailed"
                            class="flex flex-col items-center justify-center py-12 gap-4"
                        >
                            <span class="material-symbols-outlined text-4xl text-red-400">error_outline</span>
                            <p class="text-gray-500 dark:text-gray-400">
                                知乎文章生成失败
                            </p>
                            <button
                                class="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                                @click="handleGenerateContent('zhihu')"
                            >
                                <span class="material-symbols-outlined text-lg">refresh</span>
                                <span>重新生成</span>
                            </button>
                        </div>
                    </ContentSection>

                    <!-- 视频区块 -->
                    <ContentSection
                        id="video"
                        title="视频"
                        icon="videocam"
                        :is-visible="isSectionVisible('video')"
                        :is-loading="taskStatus === 'downloading' && !videoResult.video_url"
                        :loading-text="getLoadingText('video')"
                    >
                        <VideoSection
                            :src="videoDownloadUrl"
                            :title="videoResult.title"
                            :available="!!videoResult.video_url"
                            :is-processing="taskStatus === 'downloading'"
                        />
                    </ContentSection>

                    <!-- 音频区块 -->
                    <ContentSection
                        id="audio"
                        title="音频"
                        icon="music_note"
                        :is-visible="isSectionVisible('audio')"
                        :is-loading="taskStatus === 'downloading' && !videoResult.audio_url"
                        :loading-text="getLoadingText('audio')"
                    >
                        <AudioSection
                            :src="audioDownloadUrl"
                            :title="videoResult.title"
                            :available="!!videoResult.audio_url"
                            :is-processing="taskStatus === 'downloading'"
                        />
                    </ContentSection>

                    <!-- 字幕区块 -->
                    <ContentSection
                        id="subtitle"
                        title="字幕"
                        icon="subtitles"
                        :is-visible="isSectionVisible('subtitle')"
                        :is-loading="taskStatus === 'transcribing' && !videoResult.transcript"
                        :loading-text="getLoadingText('subtitle')"
                    >
                        <SubtitleSection
                            :content="videoResult.transcript"
                            :title="videoResult.title"
                            :is-loading="taskStatus === 'transcribing'"
                        />
                    </ContentSection>
                </div>
            </div>
        </div>
    </main>
</template>
