<script setup lang="ts">
import { computed } from 'vue'
import type { ComputedRef } from 'vue'
import { marked } from 'marked'
import ProgressBar from './ProgressBar.vue'
import MediaDownload from './MediaDownload.vue'
import PodcastPlayer from './PodcastPlayer.vue'
import ContentTabs from './ContentTabs.vue'
import type { TaskStatus, CurrentTab, ProgressInfo, TaskResult } from '@/types'

interface Props {
    taskId: string | null
    taskStatus?: TaskStatus
    errorMessage?: string
    progress: ProgressInfo
    result: TaskResult
    currentContent?: string
}

const props = withDefaults(defineProps<Props>(), {
    taskId: null,
    taskStatus: 'pending',
    errorMessage: '',
    currentContent: ''
})

const currentTab = defineModel<CurrentTab>('currentTab', { default: 'article' })

defineEmits<{
    retry: []
    copy: []
}>()

const isProcessing: ComputedRef<boolean> = computed(() => {
    return props.taskStatus !== 'completed' && props.taskStatus !== 'failed'
})

const isFailed: ComputedRef<boolean> = computed(() => {
    return props.taskStatus === 'failed'
})

const hasTextContent: ComputedRef<boolean> = computed(() => {
    return !!(props.result.transcript || props.result.outline || props.result.article || props.result.podcast_script)
})

const showPodcast: ComputedRef<boolean> = computed(() => {
    return !!(props.result.podcast_script || props.result.has_podcast_audio)
})

const isContentLoading: ComputedRef<boolean> = computed(() => {
    if (!isProcessing.value && !isFailed.value) {
        return false
    }
    if (currentTab.value === 'transcript') {
        return !props.result.transcript
    }
    if (currentTab.value === 'outline') {
        return !props.result.outline && isProcessing.value
    }
    if (currentTab.value === 'article') {
        return !props.result.article && isProcessing.value
    }
    if (currentTab.value === 'podcast') {
        return !props.result.podcast_script && isProcessing.value
    }
    return false
})

const contentLoadingText: ComputedRef<string> = computed(() => {
    if (currentTab.value === 'transcript') {
        if (props.taskStatus === 'downloading') return '正在下载视频，转录内容稍后显示...'
        if (props.taskStatus === 'transcribing') return '正在转录音频...'
        return '准备中...'
    }
    if (currentTab.value === 'outline' || currentTab.value === 'article') {
        if (props.taskStatus === 'downloading') return '正在下载视频...'
        if (props.taskStatus === 'transcribing') return '正在转录音频...'
        if (props.taskStatus === 'generating') return '正在生成内容...'
        return '准备中...'
    }
    if (currentTab.value === 'podcast') {
        if (props.taskStatus === 'downloading') return '正在下载视频...'
        if (props.taskStatus === 'transcribing') return '正在转录音频...'
        if (props.taskStatus === 'generating') return '正在生成内容...'
        if (props.taskStatus === 'generating_podcast') return '正在生成播客脚本...'
        if (props.taskStatus === 'synthesizing') return '正在合成播客音频...'
        return '准备中...'
    }
    return '加载中...'
})

const renderedContent: ComputedRef<string> = computed(() => {
    if (!props.currentContent) {
        if (isFailed.value) return '<p class="text-gray-500">(处理失败，无法生成内容)</p>'
        if (!isProcessing.value) {
            if (currentTab.value === 'article') return '<p class="text-gray-500">(详细内容生成失败)</p>'
            if (currentTab.value === 'outline') return '<p class="text-gray-500">(大纲生成失败)</p>'
            if (currentTab.value === 'podcast') return '<p class="text-gray-500">(播客脚本生成失败)</p>'
            return '<p class="text-gray-500">(无转录内容)</p>'
        }
        return ''
    }
    return marked.parse(props.currentContent) as string
})

const statusTitle: ComputedRef<string> = computed(() => {
    if (isFailed.value) return '转换失败'
    if (isProcessing.value) return '正在处理'
    return '转换完成'
})

const statusDescription: ComputedRef<string> = computed(() => {
    if (isFailed.value) return props.errorMessage
    if (isProcessing.value) return '请勿关闭页面，内容将逐步显示'
    return '查看生成的内容，复制或下载原始媒体文件'
})

const videoDownloadUrl: ComputedRef<string> = computed(() => props.taskId ? `api/task/${props.taskId}/video` : '')
const audioDownloadUrl: ComputedRef<string> = computed(() => props.taskId ? `api/task/${props.taskId}/audio` : '')
const podcastDownloadUrl: ComputedRef<string> = computed(() => props.taskId ? `api/task/${props.taskId}/podcast` : '')
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
                        @click="$emit('retry')"
                    >
                        <span class="truncate">重新尝试</span>
                    </button>
                </div>
            </div>

            <!-- Progress Bar -->
            <ProgressBar
                v-if="isProcessing"
                :step="progress.step"
                :text="progress.text"
                :percent="progress.percent"
            />

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
                                :available="result.has_video"
                                :is-processing="isProcessing"
                                :download-url="videoDownloadUrl"
                            />
                            <MediaDownload
                                type="audio"
                                :available="result.has_audio"
                                :is-processing="isProcessing"
                                :download-url="audioDownloadUrl"
                            />
                            <PodcastPlayer
                                v-if="showPodcast || (taskStatus === 'generating_podcast' || taskStatus === 'synthesizing')"
                                :src="podcastDownloadUrl"
                                :available="result.has_podcast_audio"
                                :is-processing="taskStatus === 'generating_podcast' || taskStatus === 'synthesizing'"
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
                    @copy="$emit('copy')"
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
