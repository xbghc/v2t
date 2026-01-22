<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { ComputedRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { marked } from 'marked'
import { useTaskStore } from '@/stores/task'
import { useResultActions, getLoadingText, type LoadingTextState } from '@/composables/useResultActions'
import { useContentVisibility } from '@/composables/useContentVisibility'
import { useNavItems } from '@/composables/useNavItems'
import type { SideNavKey } from '@/types'
import SideNavigation from './SideNavigation.vue'
import ContentSection from './ContentSection.vue'
import VideoSection from './VideoSection.vue'
import AudioSection from './AudioSection.vue'
import SubtitleSection from './SubtitleSection.vue'
import PodcastPlayer from './PodcastPlayer.vue'
import MarkdownContent from './MarkdownContent.vue'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const { handleRetry, handleGenerateContent, copyContent, scrollToSection } = useResultActions()
const { showPodcast, showArticle, showOutline, showZhihu } = useContentVisibility()
const { navItems, disabledItems } = useNavItems()

// 从 store 获取响应式状态
const {
    workspaceId,
    workspaceStatus,
    progressText,
    title,
    videoUrl,
    audioUrl,
    transcript,
    // 生成内容
    outline,
    article,
    podcastScript,
    podcastAudioUrl,
    hasPodcastAudio,
    podcastError,
    zhihuArticle,
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

// 从 URL 参数加载工作区
onMounted(async () => {
    const urlWorkspaceId = route.params.id as string
    if (urlWorkspaceId && urlWorkspaceId !== 'error') {
        if (!workspaceId.value || workspaceId.value !== urlWorkspaceId) {
            const loaded = await taskStore.loadWorkspaceById(urlWorkspaceId)
            if (!loaded) {
                router.push({ name: 'home' })
            }
        }
    }
})

// 计算属性
const isProcessing: ComputedRef<boolean> = computed(() => {
    return workspaceStatus.value !== 'ready' && workspaceStatus.value !== 'failed'
})

const isFailed: ComputedRef<boolean> = computed(() => {
    return workspaceStatus.value === 'failed'
})

const statusTitle: ComputedRef<string> = computed(() => {
    if (isFailed.value) return '转换失败'
    if (isProcessing.value) return '正在处理'
    return '转换完成'
})

// 资源 URL
const BASE_URL = import.meta.env.BASE_URL
const videoDownloadUrl: ComputedRef<string> = computed(() =>
    videoUrl.value ? `${BASE_URL}${videoUrl.value.replace(/^\//, '')}` : ''
)
const audioDownloadUrl: ComputedRef<string> = computed(() =>
    audioUrl.value ? `${BASE_URL}${audioUrl.value.replace(/^\//, '')}` : ''
)
const podcastDownloadUrl: ComputedRef<string> = computed(() =>
    podcastAudioUrl.value ? `${BASE_URL}${podcastAudioUrl.value.replace(/^\//, '')}` : ''
)

// 内容渲染
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

// 切换聚焦模式
const toggleFocus = (key: SideNavKey) => {
    focusedSection.value = focusedSection.value === key ? null : key
}

// 判断区块是否可见
const isSectionVisible = (key: SideNavKey): boolean => {
    return focusedSection.value === null || focusedSection.value === key
}

// 加载状态（用于 getLoadingText）
const loadingState = computed<LoadingTextState>(() => ({
    workspaceStatus: workspaceStatus.value,
    podcastSynthesizing: podcastSynthesizing.value,
    podcastStreaming: podcastStreaming.value,
    articleStreaming: articleStreaming.value,
    outlineStreaming: outlineStreaming.value,
    zhihuStreaming: zhihuStreaming.value
}))
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
                                v-if="title"
                                class="text-lg text-gray-600 dark:text-gray-400"
                            >
                                {{ title }}
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
                        :loading-text="getLoadingText('podcast', loadingState)"
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
                        :loading-text="getLoadingText('article', loadingState)"
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

                        <MarkdownContent
                            content-key="article"
                            :display-content="displayArticle"
                            :is-failed="articleFailed"
                            label="文章"
                            @retry="handleGenerateContent"
                        />
                    </ContentSection>

                    <!-- 大纲区块 -->
                    <ContentSection
                        v-if="showOutline"
                        id="outline"
                        title="大纲"
                        icon="format_list_bulleted"
                        :is-visible="isSectionVisible('outline')"
                        :is-loading="outlineStreaming && !displayOutline"
                        :loading-text="getLoadingText('outline', loadingState)"
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
                        :loading-text="getLoadingText('zhihu', loadingState)"
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
                        :is-loading="workspaceStatus === 'downloading' && !videoUrl"
                        :loading-text="getLoadingText('video', loadingState)"
                    >
                        <VideoSection
                            :src="videoDownloadUrl"
                            :title="title"
                            :available="!!videoUrl"
                            :is-processing="workspaceStatus === 'downloading'"
                        />
                    </ContentSection>

                    <!-- 音频区块 -->
                    <ContentSection
                        id="audio"
                        title="音频"
                        icon="music_note"
                        :is-visible="isSectionVisible('audio')"
                        :is-loading="workspaceStatus === 'downloading' && !audioUrl"
                        :loading-text="getLoadingText('audio', loadingState)"
                    >
                        <AudioSection
                            :src="audioDownloadUrl"
                            :title="title"
                            :available="!!audioUrl"
                            :is-processing="workspaceStatus === 'downloading'"
                        />
                    </ContentSection>

                    <!-- 字幕区块 -->
                    <ContentSection
                        id="subtitle"
                        title="字幕"
                        icon="subtitles"
                        :is-visible="isSectionVisible('subtitle')"
                        :is-loading="workspaceStatus === 'transcribing' && !transcript"
                        :loading-text="getLoadingText('subtitle', loadingState)"
                    >
                        <SubtitleSection
                            :content="transcript"
                            :title="title"
                            :is-loading="workspaceStatus === 'transcribing'"
                        />
                    </ContentSection>
                </div>
            </div>
        </div>
    </main>
</template>
