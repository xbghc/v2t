<script setup lang="ts">
import { computed } from 'vue'
import { useToastStore } from '@/stores/toast'

interface Props {
    content: string
    title?: string
    isLoading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
    title: '字幕',
    isLoading: false
})

const toastStore = useToastStore()

const hasContent = computed(() => !!props.content?.trim())

const copyContent = () => {
    if (!props.content) return
    navigator.clipboard.writeText(props.content).then(() => {
        toastStore.showToast('已复制到剪贴板', 'success')
    }).catch(() => {
        toastStore.showToast('复制失败，请手动选择复制', 'error')
    })
}

const downloadContent = () => {
    if (!props.content) return
    const blob = new Blob([props.content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${props.title || 'transcript'}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toastStore.showToast('下载已开始', 'success')
}
</script>

<template>
    <div class="flex flex-col gap-4">
        <!-- 加载中状态 -->
        <div
            v-if="isLoading"
            class="flex flex-col items-center justify-center py-12"
        >
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-3" />
            <span class="text-sm text-gray-500 dark:text-gray-400">正在转录...</span>
        </div>

        <!-- 无内容状态 -->
        <div
            v-else-if="!hasContent"
            class="flex flex-col items-center justify-center py-12 bg-gray-100 dark:bg-dark-bg rounded-lg"
        >
            <span class="material-symbols-outlined text-4xl text-gray-400 dark:text-gray-600 mb-3">
                subtitles_off
            </span>
            <span class="text-sm text-gray-500 dark:text-gray-400">暂无字幕内容</span>
        </div>

        <!-- 字幕内容 -->
        <template v-else>
            <!-- 操作按钮 -->
            <div class="flex items-center gap-2">
                <button
                    class="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-100 dark:bg-dark-border hover:bg-gray-200 dark:hover:bg-dark-border-light text-gray-700 dark:text-gray-300 text-sm transition-colors"
                    @click="copyContent"
                >
                    <span class="material-symbols-outlined text-lg">content_copy</span>
                    <span>复制</span>
                </button>
                <button
                    class="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-100 dark:bg-dark-border hover:bg-gray-200 dark:hover:bg-dark-border-light text-gray-700 dark:text-gray-300 text-sm transition-colors"
                    @click="downloadContent"
                >
                    <span class="material-symbols-outlined text-lg">download</span>
                    <span>下载 TXT</span>
                </button>
            </div>

            <!-- 文本内容 -->
            <div class="p-4 bg-gray-50 dark:bg-dark-bg rounded-lg border border-gray-200 dark:border-dark-border max-h-96 overflow-y-auto">
                <pre class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words font-sans leading-relaxed">{{ content }}</pre>
            </div>

            <!-- 字符统计 -->
            <div class="text-xs text-gray-400 dark:text-gray-500 text-right">
                {{ content.length }} 字符
            </div>
        </template>
    </div>
</template>
