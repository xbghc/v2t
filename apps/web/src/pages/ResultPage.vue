<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { ComputedRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/task'
import { useAuthStore } from '@/stores/auth'
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
import TimingsSection from '@/components/TimingsSection.vue'
import IconRefresh from '~icons/material-symbols/refresh'
import IconContentCopy from '~icons/material-symbols/content-copy-outline'
import IconPodcasts from '~icons/material-symbols/podcasts'
import IconArticle from '~icons/material-symbols/article-outline'
import IconFormatListBulleted from '~icons/material-symbols/format-list-bulleted'
import IconVideocam from '~icons/material-symbols/videocam-outline'
import IconSubtitles from '~icons/material-symbols/subtitles-outline'
import IconAdd from '~icons/material-symbols/add'
import IconLogout from '~icons/material-symbols/logout'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const auth = useAuthStore()
const { handleRetry, handleGenerateContent, copyContent, scrollToSection } = useResultActions()
const { showPodcast, showArticle, showOutline } = useContentVisibility()
const { navItems, disabledItems } = useNavItems()

const {
    workspaceId,
    workspaceStatus,
    progressText,
    errorMessage,
    errorKind,
    title,
    videoUrl,
    transcript,
    timings,
    seriesBvid,
    seriesIndex,
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
    outlineFailed,
    articleFailed,
    podcastFailed,
    isGenerating,
} = storeToRefs(taskStore)

const focusedSection = ref<SideNavKey | null>(null)

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

const isProcessing: ComputedRef<boolean> = computed(() =>
    workspaceStatus.value !== 'ready' && workspaceStatus.value !== 'failed',
)
const isFailed: ComputedRef<boolean> = computed(() => workspaceStatus.value === 'failed')

// 用户输入相关错误（重试无意义，应该回首页改链接）
const isInputError: ComputedRef<boolean> = computed(() => errorKind.value === 'video_too_long')

const goHome = (): void => {
    taskStore.startNew()
    router.push({ name: 'home' })
}

const handleLogout = async (): Promise<void> => {
    await auth.logout()
    router.push({ name: 'login' })
}

const statusTitle: ComputedRef<string> = computed(() => {
    if (isFailed.value) return '转换失败'
    if (workspaceStatus.value === 'pending') return '等待处理'
    if (workspaceStatus.value === 'processing') {
        if (!videoUrl.value) return '正在下载'
        return '正在转录'
    }
    if (isGenerating.value) return '正在生成'
    return '已就绪'
})

// 资源 URL
const BASE_URL = import.meta.env.BASE_URL
const videoDownloadUrl: ComputedRef<string> = computed(() =>
    videoUrl.value ? `${BASE_URL}${videoUrl.value.replace(/^\//, '')}` : '',
)
const podcastDownloadUrl: ComputedRef<string> = computed(() =>
    podcastAudioUrl.value ? `${BASE_URL}${podcastAudioUrl.value.replace(/^\//, '')}` : '',
)

// signature：时长套利（原片时长 vs 读完要点的时长）
const videoDurationSec = computed(() => Number(timings.value?.audio_duration) || 0)
const readMinutes = computed(() => {
    const text = (outline.value || '') + (article.value || '') + (podcastScript.value || '')
    if (!text) return 0
    return Math.max(1, Math.round(text.length / 400)) // 中文阅读速度 ≈ 400 字/分钟
})
const showArbitrage = computed(() =>
    !isFailed.value && videoDurationSec.value > 0 && readMinutes.value > 0,
)
const savedMinutes = computed(() =>
    Math.max(0, Math.round(videoDurationSec.value / 60) - readMinutes.value),
)
function fmtDuration(sec: number): string {
    const s = Math.round(sec)
    const m = Math.floor(s / 60)
    const ss = String(s % 60).padStart(2, '0')
    if (m >= 60) return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}:${ss}`
    return `${m}:${ss}`
}

const toggleFocus = (key: SideNavKey) => {
    focusedSection.value = focusedSection.value === key ? null : key
}
const isSectionVisible = (key: SideNavKey): boolean =>
    focusedSection.value === null || focusedSection.value === key

const loadingState = computed<LoadingTextState>(() => ({
    workspaceStatus: workspaceStatus.value,
    podcastSynthesizing: podcastSynthesizing.value,
    podcastStreaming: podcastStreaming.value,
    articleStreaming: articleStreaming.value,
    outlineStreaming: outlineStreaming.value,
    progressText: progressText.value,
}))
</script>

<template>
    <main class="flex min-h-screen bg-canvas text-ink">
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
        <div class="flex min-w-0 flex-1 flex-col">
            <!-- 顶栏 -->
            <header class="flex items-center justify-end gap-2 border-b border-line px-6 py-3">
                <button
                    class="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink transition-colors hover:border-ink-faint"
                    @click="goHome"
                >
                    <IconAdd class="text-base" />
                    新任务
                </button>
                <button
                    class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-ink-soft transition-colors hover:text-ink"
                    @click="handleLogout"
                >
                    <IconLogout class="text-base" />
                    退出
                </button>
            </header>

            <div class="flex-1 overflow-y-auto">
                <div class="mx-auto w-full max-w-4xl px-6 py-8">
                    <!-- 页面头部 -->
                    <div class="mb-8">
                        <div class="flex flex-wrap items-start justify-between gap-4">
                            <div class="min-w-0">
                                <div class="mb-2 flex items-center gap-2">
                                    <span
                                        v-if="isProcessing"
                                        class="h-2 w-2 animate-pulse rounded-full bg-signal"
                                    ></span>
                                    <span
                                        class="font-mono text-[11px] uppercase tracking-[0.2em]"
                                        :class="isFailed ? 'text-red-500' : 'text-ink-faint'"
                                    >
                                        {{ statusTitle }}
                                    </span>
                                </div>
                                <h1
                                    class="font-title text-2xl font-bold leading-tight tracking-tight"
                                    :class="title ? 'text-ink' : 'text-ink-faint'"
                                >
                                    {{ title || '处理中…' }}
                                </h1>
                            </div>

                            <div class="flex items-center gap-3">
                                <WorkspacePagesSwitcher
                                    v-if="seriesBvid && seriesIndex > 0"
                                    :bvid="seriesBvid"
                                    :current-index="seriesIndex"
                                />
                                <button
                                    v-if="isFailed && isInputError"
                                    class="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-surface transition-colors hover:bg-signal hover:text-signal-ink"
                                    @click="goHome"
                                >
                                    换个链接
                                </button>
                                <button
                                    v-else-if="isFailed"
                                    class="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-surface transition-colors hover:bg-signal hover:text-signal-ink"
                                    @click="handleRetry"
                                >
                                    <IconRefresh />
                                    重新尝试
                                </button>
                            </div>
                        </div>

                        <!-- signature：时长套利 -->
                        <div
                            v-if="showArbitrage"
                            class="mt-5 inline-flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-line bg-surface px-4 py-2.5"
                        >
                            <span class="font-mono text-[11px] uppercase tracking-wider text-ink-faint">原片</span>
                            <span class="font-mono text-sm font-semibold text-ink">{{ fmtDuration(videoDurationSec) }}</span>
                            <span class="text-ink-faint">→</span>
                            <span class="font-mono text-[11px] uppercase tracking-wider text-signal">读要点</span>
                            <span class="font-mono text-sm font-semibold text-signal">~{{ readMinutes }}min</span>
                            <span
                                v-if="savedMinutes > 0"
                                class="ml-1 border-l border-line pl-3 text-xs text-ink-soft"
                            >省下约 {{ savedMinutes }} 分钟</span>
                        </div>

                        <!-- 失败原因 -->
                        <div
                            v-if="isFailed && errorMessage"
                            class="mt-4 rounded-xl border border-red-200 bg-red-50 p-4"
                        >
                            <p class="text-sm text-red-700">{{ errorMessage }}</p>
                        </div>
                    </div>

                    <!-- 内容区块列表 -->
                    <div class="space-y-6">
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
                                    class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-ink-soft transition-colors hover:bg-line/60 hover:text-ink"
                                    @click="copyContent(podcastScript)"
                                >
                                    <IconContentCopy class="text-lg" />
                                    复制脚本
                                </button>
                            </template>

                            <PodcastPlayer
                                :src="podcastDownloadUrl"
                                :available="hasPodcastAudio"
                                :is-processing="podcastSynthesizing"
                                :error="podcastError"
                            />
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
                                    class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-ink-soft transition-colors hover:bg-line/60 hover:text-ink"
                                    @click="copyContent(article || displayArticle)"
                                >
                                    <IconContentCopy class="text-lg" />
                                    复制
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
                                    class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-ink-soft transition-colors hover:bg-line/60 hover:text-ink"
                                    @click="copyContent(outline || displayOutline)"
                                >
                                    <IconContentCopy class="text-lg" />
                                    复制
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

                        <ContentSection
                            v-if="!!videoUrl"
                            id="subtitle"
                            title="字幕"
                            :icon="IconSubtitles"
                            :is-visible="isSectionVisible('subtitle')"
                            :is-loading="workspaceStatus === 'processing' && !transcript"
                            :loading-text="getLoadingText('subtitle', loadingState)"
                        >
                            <SubtitleSection :content="transcript" :title="title" />
                        </ContentSection>

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

                        <TimingsSection :timings="timings" />
                    </div>
                </div>
            </div>
        </div>
    </main>
</template>
