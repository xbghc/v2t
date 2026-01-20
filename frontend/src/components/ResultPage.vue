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
    result,
    generateOptions,
    podcastStreaming,
    podcastSynthesizing,
    outlineStreaming,
    articleStreaming,
    displayOutline,
    displayArticle,
    displayPodcast,
    // 失败状态
    outlineFailed,
    articleFailed,
    podcastFailed
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
    result.value.video_url ? `${BASE_URL}${result.value.video_url.replace(/^\//, '')}` : ''
)
const audioDownloadUrl: ComputedRef<string> = computed(() =>
    result.value.audio_url ? `${BASE_URL}${result.value.audio_url.replace(/^\//, '')}` : ''
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

// 导航项计算
const navItems = computed<SideNavItem[]>(() => {
    const items: SideNavItem[] = []

    // 播客
    if (generateOptions.value.podcast || result.value.podcast_script || result.value.has_podcast_audio) {
        items.push({
            key: 'podcast',
            label: '播客',
            icon: 'podcasts',
            hasContent: !!result.value.podcast_script || result.value.has_podcast_audio,
            isLoading: podcastStreaming.value || podcastSynthesizing.value
        })
    }

    // 文章
    if (generateOptions.value.article || result.value.article) {
        items.push({
            key: 'article',
            label: '文章',
            icon: 'article',
            hasContent: !!result.value.article || !!displayArticle.value,
            isLoading: articleStreaming.value
        })
    }

    // 大纲
    if (generateOptions.value.outline || result.value.outline) {
        items.push({
            key: 'outline',
            label: '大纲',
            icon: 'format_list_bulleted',
            hasContent: !!result.value.outline || !!displayOutline.value,
            isLoading: outlineStreaming.value
        })
    }

    // 视频（始终显示）
    items.push({
        key: 'video',
        label: '视频',
        icon: 'videocam',
        hasContent: !!result.value.video_url,
        isLoading: taskStatus.value === 'downloading'
    })

    // 音频（始终显示）
    items.push({
        key: 'audio',
        label: '音频',
        icon: 'music_note',
        hasContent: !!result.value.audio_url,
        isLoading: taskStatus.value === 'downloading'
    })

    // 字幕（始终显示）
    items.push({
        key: 'subtitle',
        label: '字幕',
        icon: 'subtitles',
        hasContent: !!result.value.transcript,
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
    if (!generateOptions.value.podcast && !result.value.podcast_script && !result.value.has_podcast_audio) {
        items.push({
            key: 'podcast',
            label: '播客',
            icon: 'podcasts',
            hasContent: false,
            isLoading: false
        })
    }

    // 文章
    if (!generateOptions.value.article && !result.value.article) {
        items.push({
            key: 'article',
            label: '文章',
            icon: 'article',
            hasContent: false,
            isLoading: false
        })
    }

    // 大纲
    if (!generateOptions.value.outline && !result.value.outline) {
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
    if (key === 'podcast' || key === 'article' || key === 'outline') {
        taskStore.generateSingleContent(key)
        toastStore.showToast(`正在生成${key === 'podcast' ? '播客' : key === 'article' ? '文章' : '大纲'}...`, 'info')
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
    if (result.value.podcast_script || result.value.has_podcast_audio || podcastStreaming.value || podcastSynthesizing.value) return true
    // 用户选择了生成，且任务已准备好开始生成
    if (generateOptions.value.podcast && (taskStatus.value === 'ready' || taskStatus.value === 'completed')) return true
    return false
})

// 是否显示文章区块（只有在任务准备好或已有内容时才显示）
const showArticle = computed(() => {
    // 已有内容或正在生成
    if (result.value.article || articleStreaming.value) return true
    // 用户选择了生成，且任务已准备好开始生成
    if (generateOptions.value.article && (taskStatus.value === 'ready' || taskStatus.value === 'completed')) return true
    return false
})

// 是否显示大纲区块（只有在任务准备好或已有内容时才显示）
const showOutline = computed(() => {
    // 已有内容或正在生成
    if (result.value.outline || outlineStreaming.value) return true
    // 用户选择了生成，且任务已准备好开始生成
    if (generateOptions.value.outline && (taskStatus.value === 'ready' || taskStatus.value === 'completed')) return true
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
                                v-if="result.title"
                                class="text-lg text-gray-600 dark:text-gray-400"
                            >
                                {{ result.title }}
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
                                v-if="result.podcast_script"
                                class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-border rounded-lg transition-colors"
                                @click="copyContent(result.podcast_script)"
                            >
                                <span class="material-symbols-outlined text-lg">content_copy</span>
                                <span>复制脚本</span>
                            </button>
                        </template>

                        <!-- 播客播放器 -->
                        <PodcastPlayer
                            :src="podcastDownloadUrl"
                            :available="result.has_podcast_audio"
                            :is-processing="podcastSynthesizing"
                            :error="result.podcast_error"
                        />

                        <!-- 播客脚本 -->
                        <div
                            v-if="displayPodcast"
                            class="mt-6 prose prose-sm dark:prose-invert max-w-none"
                            v-html="renderedPodcastScript"
                        />
                        <!-- 生成失败：显示失败提示和重试按钮 -->
                        <div
                            v-else-if="podcastFailed && !result.has_podcast_audio"
                            class="flex flex-col items-center justify-center py-12 gap-4"
                        >
                            <span class="material-symbols-outlined text-4xl text-red-400">error_outline</span>
                            <p class="text-gray-500 dark:text-gray-400">播客生成失败</p>
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
                                v-if="result.article || displayArticle"
                                class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-border rounded-lg transition-colors"
                                @click="copyContent(result.article || displayArticle)"
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
                            <p class="text-gray-500 dark:text-gray-400">文章生成失败</p>
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
                                v-if="result.outline || displayOutline"
                                class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-border rounded-lg transition-colors"
                                @click="copyContent(result.outline || displayOutline)"
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
                            <p class="text-gray-500 dark:text-gray-400">大纲生成失败</p>
                            <button
                                class="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                                @click="handleGenerateContent('outline')"
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
                        :is-loading="taskStatus === 'downloading' && !result.video_url"
                        :loading-text="getLoadingText('video')"
                    >
                        <VideoSection
                            :src="videoDownloadUrl"
                            :title="result.title"
                            :available="!!result.video_url"
                            :is-processing="taskStatus === 'downloading'"
                        />
                    </ContentSection>

                    <!-- 音频区块 -->
                    <ContentSection
                        id="audio"
                        title="音频"
                        icon="music_note"
                        :is-visible="isSectionVisible('audio')"
                        :is-loading="taskStatus === 'downloading' && !result.audio_url"
                        :loading-text="getLoadingText('audio')"
                    >
                        <AudioSection
                            :src="audioDownloadUrl"
                            :title="result.title"
                            :available="!!result.audio_url"
                            :is-processing="taskStatus === 'downloading'"
                        />
                    </ContentSection>

                    <!-- 字幕区块 -->
                    <ContentSection
                        id="subtitle"
                        title="字幕"
                        icon="subtitles"
                        :is-visible="isSectionVisible('subtitle')"
                        :is-loading="taskStatus === 'transcribing' && !result.transcript"
                        :loading-text="getLoadingText('subtitle')"
                    >
                        <SubtitleSection
                            :content="result.transcript"
                            :title="result.title"
                            :is-loading="taskStatus === 'transcribing'"
                        />
                    </ContentSection>
                </div>
            </div>
        </div>
    </main>
</template>
