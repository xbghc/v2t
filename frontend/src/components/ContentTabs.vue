<script setup>
defineProps({
    currentTab: {
        type: String,
        required: true
    },
    isLoading: {
        type: Boolean,
        default: false
    },
    loadingText: {
        type: String,
        default: '加载中...'
    },
    renderedContent: {
        type: String,
        default: ''
    }
})

defineEmits(['update:currentTab', 'copy'])

const tabs = [
    { key: 'article', label: '详细内容' },
    { key: 'outline', label: '大纲' },
    { key: 'transcript', label: '原始转录' }
]
</script>

<template>
    <div class="lg:col-span-2 flex flex-col bg-white dark:bg-dark-bg rounded-xl border border-gray-200 dark:border-dark-border">
        <div class="flex flex-col flex-1">
            <!-- Tabs & Copy Button Wrapper -->
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center p-4 border-b border-gray-200 dark:border-dark-border">
                <!-- Tabs -->
                <div class="flex border-b border-transparent sm:border-b-0 -mb-px">
                    <div class="flex gap-4 sm:gap-8">
                        <a
                            v-for="tab in tabs"
                            :key="tab.key"
                            href="#"
                            @click.prevent="$emit('update:currentTab', tab.key)"
                            class="flex flex-col items-center justify-center border-b-3 pb-3.25 pt-2 transition-colors"
                            :class="currentTab === tab.key ? 'border-b-primary' : 'border-b-transparent'"
                        >
                            <p
                                class="text-sm font-bold leading-normal tracking-tight-sm"
                                :class="currentTab === tab.key ? 'text-gray-900 dark:text-white' : 'text-gray-500 dark:text-dark-text-muted'"
                            >{{ tab.label }}</p>
                        </a>
                    </div>
                </div>
                <!-- Copy Button -->
                <div class="pt-4 sm:pt-0 w-full sm:w-auto flex justify-end">
                    <button
                        @click="$emit('copy')"
                        :disabled="isLoading"
                        :class="isLoading ? 'bg-gray-100 dark:bg-dark-card text-gray-400 dark:text-gray-600 cursor-not-allowed' : 'bg-gray-200 dark:bg-dark-border text-gray-900 dark:text-white cursor-pointer hover:bg-gray-300 dark:hover:bg-dark-border-light'"
                        class="flex min-w-btn max-w-input items-center justify-center overflow-hidden rounded-lg h-10 px-4 gap-2 text-sm font-bold leading-normal tracking-tight-sm transition-colors"
                    >
                        <span class="material-symbols-outlined text-xl">content_copy</span>
                        <span class="truncate">复制内容</span>
                    </button>
                </div>
            </div>
            <!-- Content Area -->
            <div class="p-6 text-gray-600 dark:text-dark-text leading-relaxed text-base overflow-y-auto flex-1" style="max-height: 600px;">
                <!-- 加载中状态 -->
                <div v-if="isLoading" class="flex flex-col items-center justify-center py-12 gap-4">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    <p class="text-gray-500 dark:text-gray-400 text-sm">{{ loadingText }}</p>
                </div>
                <!-- 实际内容 -->
                <div v-else class="prose prose-sm md:prose-base dark:prose-invert max-w-none" v-html="renderedContent"></div>
            </div>
        </div>
    </div>
</template>
