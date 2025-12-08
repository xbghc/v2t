<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({
    taskId: String,
    taskStatus: String,
    currentTab: String,
    errorMessage: String,
    progress: Object,
    result: Object,
    isProcessing: Boolean,
    isFailed: Boolean,
    hasTextContent: Boolean,
    currentContent: String,
    isContentLoading: Boolean,
    contentLoadingText: String
})

const emit = defineEmits(['startNew', 'retryTask', 'copyContent', 'update:currentTab'])

const renderedContent = computed(() => {
    if (!props.currentContent) {
        if (props.isFailed) return '<p class="text-gray-500">(处理失败，无法生成内容)</p>'
        if (!props.isProcessing) {
            if (props.currentTab === 'article') return '<p class="text-gray-500">(详细内容生成失败)</p>'
            if (props.currentTab === 'outline') return '<p class="text-gray-500">(大纲生成失败)</p>'
            return '<p class="text-gray-500">(无转录内容)</p>'
        }
        return ''
    }
    return marked.parse(props.currentContent)
})
</script>

<template>
    <div class="relative flex min-h-screen w-full flex-col">
        <div class="layout-container flex h-full grow flex-col">
            <!-- TopNavBar -->
            <header class="flex items-center justify-between whitespace-nowrap border-b border-solid border-gray-200 dark:border-b-[#282e39] px-6 sm:px-10 lg:px-20 py-3 bg-white dark:bg-[#111318]">
                <div class="flex items-center gap-4 text-gray-800 dark:text-white">
                    <div class="size-6 text-primary">
                        <svg fill="currentColor" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                            <path clip-rule="evenodd" d="M47.2426 24L24 47.2426L0.757355 24L24 0.757355L47.2426 24ZM12.2426 21H35.7574L24 9.24264L12.2426 21Z" fill-rule="evenodd"></path>
                        </svg>
                    </div>
                    <h2 class="text-gray-900 dark:text-white text-lg font-bold leading-tight tracking-[-0.015em]">V2T 视频转文字</h2>
                </div>
                <button @click="emit('startNew')" class="flex min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold leading-normal tracking-[0.015em] hover:bg-primary/90 transition-colors">
                    <span class="truncate">新建转换</span>
                </button>
            </header>
            <main class="px-6 sm:px-10 lg:px-20 flex flex-1 justify-center py-5 sm:py-8 md:py-10">
                <div class="layout-content-container flex flex-col w-full max-w-7xl flex-1">
                    <!-- PageHeading -->
                    <div class="flex flex-wrap justify-between gap-3 p-4">
                        <div class="flex min-w-72 flex-col gap-2">
                            <p class="text-gray-900 dark:text-white text-4xl font-black leading-tight tracking-[-0.033em]">
                                {{ isFailed ? '转换失败' : (isProcessing ? '正在处理' : '转换完成') }}
                            </p>
                            <p class="text-gray-500 dark:text-[#9da6b9] text-base font-normal leading-normal">
                                {{ isFailed ? errorMessage : (isProcessing ? '请勿关闭页面，内容将逐步显示' : '查看生成的内容，复制或下载原始媒体文件') }}
                            </p>
                        </div>
                        <div v-if="isFailed" class="flex items-center">
                            <button @click="emit('retryTask')" class="flex min-w-[84px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold leading-normal tracking-[0.015em] hover:bg-primary/90 transition-colors">
                                <span class="truncate">重新尝试</span>
                            </button>
                        </div>
                    </div>
                    <!-- Progress Bar (processing) -->
                    <div v-if="isProcessing" class="px-4 pb-4">
                        <div class="bg-white dark:bg-[#1c1f27] border border-gray-200 dark:border-[#282e39] rounded-lg p-4">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ progress.step }}</span>
                                <span class="text-sm text-gray-500 dark:text-gray-400">{{ progress.text }}</span>
                            </div>
                            <div class="w-full bg-gray-200 dark:bg-[#3b4354] rounded-full h-2">
                                <div class="bg-primary h-2 rounded-full transition-all duration-500" :style="{ width: progress.percent + '%' }"></div>
                            </div>
                        </div>
                    </div>
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 p-4 mt-4">
                        <!-- Left Column: Video Info -->
                        <aside class="lg:col-span-1 flex flex-col gap-6">
                            <div class="flex flex-col gap-4">
                                <div class="flex flex-col gap-1">
                                    <p class="text-gray-900 dark:text-white text-lg font-bold leading-tight">{{ result.title || '视频标题' }}</p>
                                </div>
                                <div class="flex flex-col sm:flex-row lg:flex-col gap-3">
                                    <!-- 下载视频按钮 -->
                                    <a v-if="result.has_video" :href="'/api/task/' + taskId + '/video'" class="flex w-full min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-gray-200 dark:bg-[#282e39] text-gray-900 dark:text-white gap-2 text-sm font-medium leading-normal hover:bg-gray-300 dark:hover:bg-[#3b4354] transition-colors">
                                        <span class="material-symbols-outlined text-lg">videocam</span>
                                        <span class="truncate">下载视频</span>
                                    </a>
                                    <button v-else disabled class="flex w-full min-w-[84px] max-w-[480px] items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-gray-100 dark:bg-[#1c1f27] text-gray-400 dark:text-gray-600 gap-2 text-sm font-medium leading-normal cursor-not-allowed">
                                        <span class="material-symbols-outlined text-lg animate-pulse" v-if="isProcessing">hourglass_empty</span>
                                        <span class="material-symbols-outlined text-lg" v-else>videocam_off</span>
                                        <span class="truncate">{{ isProcessing ? '下载中...' : '视频不可用' }}</span>
                                    </button>
                                    <!-- 下载音频按钮 -->
                                    <a v-if="result.has_audio" :href="'/api/task/' + taskId + '/audio'" class="flex w-full min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-gray-200 dark:bg-[#282e39] text-gray-900 dark:text-white gap-2 text-sm font-medium leading-normal hover:bg-gray-300 dark:hover:bg-[#3b4354] transition-colors">
                                        <span class="material-symbols-outlined text-lg">audiotrack</span>
                                        <span class="truncate">下载音频</span>
                                    </a>
                                    <button v-else disabled class="flex w-full min-w-[84px] max-w-[480px] items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-gray-100 dark:bg-[#1c1f27] text-gray-400 dark:text-gray-600 gap-2 text-sm font-medium leading-normal cursor-not-allowed">
                                        <span class="material-symbols-outlined text-lg animate-pulse" v-if="isProcessing">hourglass_empty</span>
                                        <span class="material-symbols-outlined text-lg" v-else>music_off</span>
                                        <span class="truncate">{{ isProcessing ? '转录中...' : '音频不可用' }}</span>
                                    </button>
                                </div>
                            </div>
                        </aside>
                        <!-- Right Column: Content (仅在有内容或处理中时显示) -->
                        <div v-if="hasTextContent || isProcessing" class="lg:col-span-2 flex flex-col bg-white dark:bg-[#111318] rounded-xl border border-gray-200 dark:border-[#282e39]">
                            <div class="flex flex-col flex-1">
                                <!-- Tabs & Copy Button Wrapper -->
                                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center p-4 border-b border-gray-200 dark:border-[#282e39]">
                                    <!-- Tabs -->
                                    <div class="flex border-b border-transparent sm:border-b-0 -mb-px">
                                        <div class="flex gap-4 sm:gap-8">
                                            <a href="#" @click.prevent="emit('update:currentTab', 'article')" class="flex flex-col items-center justify-center border-b-[3px] pb-[13px] pt-2 transition-colors" :class="currentTab === 'article' ? 'border-b-primary' : 'border-b-transparent'">
                                                <p class="text-sm font-bold leading-normal tracking-[0.015em]" :class="currentTab === 'article' ? 'text-gray-900 dark:text-white' : 'text-gray-500 dark:text-[#9da6b9]'">详细内容</p>
                                            </a>
                                            <a href="#" @click.prevent="emit('update:currentTab', 'outline')" class="flex flex-col items-center justify-center border-b-[3px] pb-[13px] pt-2 transition-colors" :class="currentTab === 'outline' ? 'border-b-primary' : 'border-b-transparent'">
                                                <p class="text-sm font-bold leading-normal tracking-[0.015em]" :class="currentTab === 'outline' ? 'text-gray-900 dark:text-white' : 'text-gray-500 dark:text-[#9da6b9]'">大纲</p>
                                            </a>
                                            <a href="#" @click.prevent="emit('update:currentTab', 'transcript')" class="flex flex-col items-center justify-center border-b-[3px] pb-[13px] pt-2 transition-colors" :class="currentTab === 'transcript' ? 'border-b-primary' : 'border-b-transparent'">
                                                <p class="text-sm font-bold leading-normal tracking-[0.015em]" :class="currentTab === 'transcript' ? 'text-gray-900 dark:text-white' : 'text-gray-500 dark:text-[#9da6b9]'">原始转录</p>
                                            </a>
                                        </div>
                                    </div>
                                    <!-- Copy Button -->
                                    <div class="pt-4 sm:pt-0 w-full sm:w-auto flex justify-end">
                                        <button @click="emit('copyContent')" :disabled="isContentLoading" :class="isContentLoading ? 'bg-gray-100 dark:bg-[#1c1f27] text-gray-400 dark:text-gray-600 cursor-not-allowed' : 'bg-gray-200 dark:bg-[#282e39] text-gray-900 dark:text-white cursor-pointer hover:bg-gray-300 dark:hover:bg-[#3b4354]'" class="flex min-w-[84px] max-w-[480px] items-center justify-center overflow-hidden rounded-lg h-10 px-4 gap-2 text-sm font-bold leading-normal tracking-[0.015em] transition-colors">
                                            <span class="material-symbols-outlined text-xl">content_copy</span>
                                            <span class="truncate">复制内容</span>
                                        </button>
                                    </div>
                                </div>
                                <!-- Content Area -->
                                <div class="p-6 text-gray-600 dark:text-[#c4c9d4] leading-relaxed text-base overflow-y-auto flex-1" style="max-height: 600px;">
                                    <!-- 加载中状态 -->
                                    <div v-if="isContentLoading" class="flex flex-col items-center justify-center py-12 gap-4">
                                        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                                        <p class="text-gray-500 dark:text-gray-400 text-sm">{{ contentLoadingText }}</p>
                                    </div>
                                    <!-- 实际内容 -->
                                    <div v-else class="prose prose-sm md:prose-base dark:prose-invert max-w-none" v-html="renderedContent"></div>
                                </div>
                            </div>
                        </div>
                        <!-- 仅下载模式提示 -->
                        <div v-else-if="!isFailed" class="lg:col-span-2 flex flex-col items-center justify-center bg-white dark:bg-[#111318] rounded-xl border border-gray-200 dark:border-[#282e39] p-12">
                            <span class="material-symbols-outlined text-5xl text-gray-400 dark:text-gray-600 mb-4">download_done</span>
                            <p class="text-gray-600 dark:text-gray-400 text-center">仅下载模式，无文字内容</p>
                            <p class="text-gray-500 dark:text-gray-500 text-sm text-center mt-2">请使用左侧按钮下载视频或音频文件</p>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    </div>
</template>
