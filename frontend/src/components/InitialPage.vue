<script setup lang="ts">
const url = defineModel<string>('url', { default: '' })
const downloadOnly = defineModel<boolean>('downloadOnly', { default: false })

defineEmits<{
    submit: []
}>()
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
                <!-- 仅下载选项 -->
                <label class="flex items-center gap-2 cursor-pointer select-none">
                    <input
                        v-model="downloadOnly"
                        type="checkbox"
                        class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-primary focus:ring-primary focus:ring-offset-0 bg-white dark:bg-dark-card"
                    >
                    <span class="text-sm text-gray-600 dark:text-gray-400">仅下载音视频，不转录</span>
                </label>
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
