<script setup lang="ts">
import { toRef } from 'vue'
import { useMarkdown } from '@/composables/useMarkdown'
import type { GeneratableContentKey } from '@/types'

const props = defineProps<{
    /** 内容类型标识 */
    contentKey: GeneratableContentKey
    /** 显示的内容（可能是流式内容） */
    displayContent: string
    /** 是否生成失败 */
    isFailed: boolean
    /** 内容标签（用于失败提示） */
    label: string
}>()

const emit = defineEmits<{
    /** 重试生成 */
    retry: [key: GeneratableContentKey]
}>()

const renderedContent = useMarkdown(toRef(props, 'displayContent'))
</script>

<template>
    <!-- Markdown 内容 -->
    <div
        v-if="displayContent"
        class="prose prose-sm md:prose-base dark:prose-invert max-w-none"
        v-html="renderedContent"
    />

    <!-- 生成失败：显示失败提示和重试按钮 -->
    <div
        v-else-if="isFailed"
        class="flex flex-col items-center justify-center py-12 gap-4"
    >
        <span class="material-symbols-outlined text-4xl text-red-400">error_outline</span>
        <p class="text-gray-500 dark:text-gray-400">
            {{ label }}生成失败
        </p>
        <button
            class="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
            @click="emit('retry', contentKey)"
        >
            <span class="material-symbols-outlined text-lg">refresh</span>
            <span>重新生成</span>
        </button>
    </div>
</template>
