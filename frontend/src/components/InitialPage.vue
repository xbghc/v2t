<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useTaskStore } from '@/stores/task'

const url = defineModel<string>('url', { default: '' })

defineEmits<{
    submit: []
}>()

const taskStore = useTaskStore()
const showAdvanced = ref(false)

// 提示文字：当所有选项都未勾选时显示
const showDownloadOnlyHint = computed(() => taskStore.isDownloadOnly)

onMounted(() => {
    taskStore.loadPrompts()
})
</script>

<template>
    <main class="flex-grow">
        <!-- HeroSection -->
        <div class="@container pt-16 sm:pt-24 pb-12 sm:pb-16">
            <div class="flex min-h-hero flex-col gap-6 items-center justify-center p-4 text-center">
                <div class="flex flex-col gap-2">
                    <h1 class="text-4xl font-black leading-tight tracking-tight-lg text-gray-900 dark:text-white @[480px]:text-5xl">
                        一键提取视频精华
                    </h1>
                    <h2 class="text-sm font-normal leading-normal text-gray-600 dark:text-gray-300 @[480px]:text-base">
                        粘贴视频链接，自动生成文字版内容、大纲和原始转录
                    </h2>
                </div>
                <label class="flex flex-col min-w-40 h-14 w-full max-w-input @[480px]:h-16">
                    <div class="flex w-full flex-1 items-stretch rounded-lg h-full shadow-sm">
                        <div class="text-gray-400 dark:text-dark-text-muted flex border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card items-center justify-center pl-4 rounded-l-lg border-r-0">
                            <span class="material-symbols-outlined text-xl">link</span>
                        </div>
                        <input
                            v-model="url"
                            class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden text-gray-900 dark:text-white focus:outline-none focus:ring-0 border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card h-full placeholder:text-gray-400 dark:placeholder:text-dark-text-muted px-3_75 border-r-0 border-l-0 text-sm font-normal leading-normal @[480px]:text-base"
                            placeholder="https://www.bilibili.com/video/..."
                            @keypress.enter="$emit('submit')"
                        >
                        <div class="flex items-center justify-center rounded-r-lg border-l-0 border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card pr-2">
                            <button
                                class="flex min-w-btn max-w-input cursor-pointer items-center justify-center overflow-hidden rounded-md h-10 px-4 @[480px]:h-12 @[480px]:px-5 bg-primary text-white text-sm font-bold leading-normal tracking-tight-sm hover:bg-primary/90 focus:ring-0 focus:outline-none @[480px]:text-base"
                                @click="$emit('submit')"
                            >
                                <span class="truncate">开始转换</span>
                            </button>
                        </div>
                    </div>
                </label>
                <!-- 生成选项多选组 -->
                <div class="flex flex-col items-center gap-2">
                    <div class="flex items-center gap-4">
                        <span class="text-sm text-gray-600 dark:text-gray-400">生成内容：</span>
                        <label class="flex items-center gap-1.5 cursor-pointer select-none">
                            <input
                                v-model="taskStore.generateOptions.outline"
                                type="checkbox"
                                class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-primary focus:ring-primary focus:ring-offset-0 bg-white dark:bg-dark-card"
                            >
                            <span class="text-sm text-gray-700 dark:text-gray-300">大纲</span>
                        </label>
                        <label class="flex items-center gap-1.5 cursor-pointer select-none">
                            <input
                                v-model="taskStore.generateOptions.article"
                                type="checkbox"
                                class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-primary focus:ring-primary focus:ring-offset-0 bg-white dark:bg-dark-card"
                            >
                            <span class="text-sm text-gray-700 dark:text-gray-300">文章</span>
                        </label>
                        <label class="flex items-center gap-1.5 cursor-pointer select-none">
                            <input
                                v-model="taskStore.generateOptions.podcast"
                                type="checkbox"
                                class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-primary focus:ring-primary focus:ring-offset-0 bg-white dark:bg-dark-card"
                            >
                            <span class="text-sm text-gray-700 dark:text-gray-300">播客</span>
                        </label>
                    </div>
                    <p
                        v-if="showDownloadOnlyHint"
                        class="text-xs text-gray-500 dark:text-gray-400"
                    >
                        未选择任何生成选项，将仅下载音视频
                    </p>
                </div>

                <!-- 高级选项 -->
                <button
                    type="button"
                    class="text-sm text-gray-500 dark:text-gray-400 hover:text-primary dark:hover:text-primary flex items-center gap-1 cursor-pointer transition-colors duration-200"
                    @click="showAdvanced = !showAdvanced"
                >
                    <span
                        class="material-symbols-outlined text-base transition-transform duration-200"
                        :class="{ 'rotate-90': showAdvanced }"
                    >chevron_right</span>
                    <span>高级选项 - 自定义提示词</span>
                </button>
            </div>
        </div>

        <!-- 高级选项面板 -->
        <div
            v-if="showAdvanced && taskStore.promptsLoaded"
            class="px-4 pb-8"
        >
            <div class="max-w-2xl mx-auto space-y-6">
                <!-- 大纲提示词 -->
                <div class="bg-white dark:bg-dark-card rounded-lg border border-gray-200 dark:border-dark-border-light p-4">
                    <div class="flex items-center justify-between mb-3">
                        <h4 class="text-sm font-semibold text-gray-900 dark:text-white">
                            大纲生成提示词
                        </h4>
                        <button
                            type="button"
                            class="text-xs text-gray-500 hover:text-primary dark:text-gray-400 dark:hover:text-primary cursor-pointer transition-colors"
                            @click="taskStore.resetOutlinePrompts()"
                        >
                            重置为默认
                        </button>
                    </div>
                    <div class="space-y-3">
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">系统提示词</label>
                            <textarea
                                v-model="taskStore.prompts.outlineSystem"
                                rows="8"
                                class="w-full text-sm rounded-lg border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card text-gray-900 dark:text-white p-3 placeholder:text-gray-400 dark:placeholder:text-dark-text-muted focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary resize-none transition-colors"
                            />
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">用户提示词 <span class="text-gray-400 dark:text-dark-text-muted">(使用 {content} 表示转录内容)</span></label>
                            <textarea
                                v-model="taskStore.prompts.outlineUser"
                                rows="3"
                                class="w-full text-sm rounded-lg border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card text-gray-900 dark:text-white p-3 placeholder:text-gray-400 dark:placeholder:text-dark-text-muted focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary resize-none transition-colors"
                            />
                        </div>
                    </div>
                </div>

                <!-- 文章提示词 -->
                <div class="bg-white dark:bg-dark-card rounded-lg border border-gray-200 dark:border-dark-border-light p-4">
                    <div class="flex items-center justify-between mb-3">
                        <h4 class="text-sm font-semibold text-gray-900 dark:text-white">
                            文章生成提示词
                        </h4>
                        <button
                            type="button"
                            class="text-xs text-gray-500 hover:text-primary dark:text-gray-400 dark:hover:text-primary cursor-pointer transition-colors"
                            @click="taskStore.resetArticlePrompts()"
                        >
                            重置为默认
                        </button>
                    </div>
                    <div class="space-y-3">
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">系统提示词</label>
                            <textarea
                                v-model="taskStore.prompts.articleSystem"
                                rows="8"
                                class="w-full text-sm rounded-lg border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card text-gray-900 dark:text-white p-3 placeholder:text-gray-400 dark:placeholder:text-dark-text-muted focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary resize-none transition-colors"
                            />
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">用户提示词 <span class="text-gray-400 dark:text-dark-text-muted">(使用 {content} 表示转录内容)</span></label>
                            <textarea
                                v-model="taskStore.prompts.articleUser"
                                rows="3"
                                class="w-full text-sm rounded-lg border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card text-gray-900 dark:text-white p-3 placeholder:text-gray-400 dark:placeholder:text-dark-text-muted focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary resize-none transition-colors"
                            />
                        </div>
                    </div>
                </div>

                <!-- 播客提示词 -->
                <div class="bg-white dark:bg-dark-card rounded-lg border border-gray-200 dark:border-dark-border-light p-4">
                    <div class="flex items-center justify-between mb-3">
                        <h4 class="text-sm font-semibold text-gray-900 dark:text-white">
                            播客脚本生成提示词
                        </h4>
                        <button
                            type="button"
                            class="text-xs text-gray-500 hover:text-primary dark:text-gray-400 dark:hover:text-primary cursor-pointer transition-colors"
                            @click="taskStore.resetPodcastPrompts()"
                        >
                            重置为默认
                        </button>
                    </div>
                    <div class="space-y-3">
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">系统提示词</label>
                            <textarea
                                v-model="taskStore.prompts.podcastSystem"
                                rows="8"
                                class="w-full text-sm rounded-lg border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card text-gray-900 dark:text-white p-3 placeholder:text-gray-400 dark:placeholder:text-dark-text-muted focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary resize-none transition-colors"
                            />
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">用户提示词 <span class="text-gray-400 dark:text-dark-text-muted">(使用 {content} 表示转录内容)</span></label>
                            <textarea
                                v-model="taskStore.prompts.podcastUser"
                                rows="3"
                                class="w-full text-sm rounded-lg border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card text-gray-900 dark:text-white p-3 placeholder:text-gray-400 dark:placeholder:text-dark-text-muted focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary resize-none transition-colors"
                            />
                        </div>
                    </div>
                </div>

                <!-- 重置所有 -->
                <div class="text-center">
                    <button
                        type="button"
                        class="text-xs text-gray-500 hover:text-red-500 dark:text-gray-400 dark:hover:text-red-400 cursor-pointer transition-colors"
                        @click="taskStore.resetPrompts()"
                    >
                        重置所有提示词为默认值
                    </button>
                </div>
            </div>
        </div>
        <!-- SectionHeader -->
        <div class="py-8">
            <h4 class="text-sm font-bold leading-normal tracking-tight-sm px-4 py-2 text-center text-gray-500 dark:text-dark-text-muted">
                支持主流视频平台
            </h4>
        </div>
        <!-- Platform Icons -->
        <div class="flex flex-wrap gap-8 px-4 items-center justify-center opacity-60">
            <span class="text-gray-600 dark:text-gray-400 text-sm font-medium">哔哩哔哩</span>
            <span class="text-gray-600 dark:text-gray-400 text-sm font-medium">抖音</span>
            <span class="text-gray-600 dark:text-gray-400 text-sm font-medium">小红书</span>
            <span class="text-gray-600 dark:text-gray-400 text-sm font-medium">YouTube</span>
        </div>
    </main>
</template>
