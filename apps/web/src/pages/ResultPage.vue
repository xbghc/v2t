<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { ComputedRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/task'
import { useResultActions, getLoadingText, type LoadingTextState } from '@/composables/useResultActions'
import { useContentVisibility } from '@/composables/useContentVisibility'
import { useNavItems } from '@/composables/useNavItems'
import type { SideNavKey } from '@/types'
import SideNavigation from '@/components/SideNavigation.vue'
import ContentSection from '@/components/ContentSection.vue'
import VideoSection from '@/components/VideoSection.vue'
import SubtitleSection from '@/components/SubtitleSection.vue'
import PodcastPlayer from '@/components/PodcastPlayer.vue'
import MarkdownContent from '@/components/MarkdownContent.vue'
import WorkspacePagesSwitcher from '@/components/WorkspacePagesSwitcher.vue'
import IconRefresh from '~icons/material-symbols/refresh'
import IconContentCopy from '~icons/material-symbols/content-copy-outline'
import IconPodcasts from '~icons/material-symbols/podcasts'
import IconArticle from '~icons/material-symbols/article-outline'
import IconFormatListBulleted from '~icons/material-symbols/format-list-bulleted'
import IconVideocam from '~icons/material-symbols/videocam-outline'
import IconSubtitles from '~icons/material-symbols/subtitles-outline'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const { handleRetry, handleGenerateContent, copyContent, scrollToSection } = useResultActions()
const { showPodcast, showArticle, showOutline } = useContentVisibility()
const { navItems, disabledItems } = useNavItems()

// 从 store 获取响应式状态
const {
    workspaceId,
    workspaceStatus,
    progressText,
    title,
    videoUrl,
    transcript,
    seriesBvid,
    seriesIndex,
    // 生成内容
    outline,
    article,
    podcastScript,
    podcastAudioUrl,
    hasPodcastAudio,
    podcastError,
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
    podcastFailed,
    // 派生状态
    isGenerating,
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
    if (workspaceStatus.value === 'pending') return '等待处理'
    if (workspaceStatus.value === 'processing') {
        // 通过资源就绪状态细分阶段
        if (!videoUrl.value) return '正在下载'
        return '正在转录'
    }
    if (isGenerating.value) return '正在生成'
    return '转换完成'
})

// 资源 URL
const BASE_URL = import.meta.env.BASE_URL
const videoDownloadUrl: ComputedRef<string> = computed(() =>
    videoUrl.value ? `${BASE_URL}${videoUrl.value.replace(/^\//, '')}` : ''
)
const podcastDownloadUrl: ComputedRef<string> = computed(() =>
    podcastAudioUrl.value ? `${BASE_URL}${podcastAudioUrl.value.replace(/^\//, '')}` : ''
)

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
    outlineStreaming: outlineStreaming.value
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

                        <div class="flex items-center gap-3">
                            <!-- 切换分 P（仅 B 站合集场景） -->
                            <WorkspacePagesSwitcher
                                v-if="seriesBvid && seriesIndex > 0"
                                :bvid="seriesBvid"
                                :current-index="seriesIndex"
                            />

                            <!-- 重试按钮 -->
                            <button
                                v-if="isFailed"
                                class="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                                @click="handleRetry"
                            >
                                <IconRefresh />
                                <span>重新尝试</span>
                            </button>
                        </div>
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
                        :icon="IconPodcasts"
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
                                <IconContentCopy class="text-lg" />
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
                        <MarkdownContent
                            v-if="displayPodcast || (podcastFailed && !hasPodcastAudio)"
                            content-key="podcast"
                            :display-content="displayPodcast"
                            :is-failed="podcastFailed && !hasPodcastAudio"
                            label="播客"
                            class="mt-6"
                            @retry="handleGenerateContent"
                        />
                    </ContentSection>

                    <!-- 文章区块 -->
                    <ContentSection
                        v-if="showArticle"
                        id="article"
                        title="文章"
                        :icon="IconArticle"
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
                                <IconContentCopy class="text-lg" />
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
                        :icon="IconFormatListBulleted"
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
                                <IconContentCopy class="text-lg" />
                                <span>复制</span>
                            </button>
                        </template>

                        <MarkdownContent
                            content-key="outline"
                            :display-content="displayOutline"
                            :is-failed="outlineFailed"
                            label="大纲"
                            @retry="handleGenerateContent"
                        />
                    </ContentSection>

                    <!-- 字幕区块（视频下载完后出现，loading 时显示后端转录进度） -->
                    <ContentSection
                        v-if="!!videoUrl"
                        id="subtitle"
                        title="字幕"
                        :icon="IconSubtitles"
                        :is-visible="isSectionVisible('subtitle')"
                        :is-loading="workspaceStatus === 'processing' && !transcript"
                        :loading-text="progressText || '正在转录...'"
                    >
                        <SubtitleSection
                            :content="transcript"
                            :title="title"
                        />
                    </ContentSection>

                    <!-- 视频区块（始终显示，最初阶段唯一可见的块） -->
                    <ContentSection
                        id="video"
                        title="视频"
                        :icon="IconVideocam"
                        :is-visible="isSectionVisible('video')"
                        :is-loading="workspaceStatus === 'processing' && !videoUrl"
                        :loading-text="getLoadingText('video', loadingState)"
                    >
                        <VideoSection
                            :src="videoDownloadUrl"
                            :title="title"
                            :available="!!videoUrl"
                            :is-processing="isProcessing"
                        />
                    </ContentSection>
                </div>
            </div>
        </div>
    </main>
</template>
