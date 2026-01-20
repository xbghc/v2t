<script setup lang="ts">
interface Props {
    id: string
    title: string
    icon: string
    isVisible?: boolean
    isLoading?: boolean
    loadingText?: string
}

withDefaults(defineProps<Props>(), {
    isVisible: true,
    isLoading: false,
    loadingText: '加载中...'
})
</script>

<template>
    <section
        v-show="isVisible"
        :id="`section-${id}`"
        class="scroll-mt-20 bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border overflow-hidden transition-all duration-300"
    >
        <!-- 标题栏 -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-bg">
            <div class="flex items-center gap-3">
                <span class="material-symbols-outlined text-xl text-primary">
                    {{ icon }}
                </span>
                <h3 class="text-base font-semibold text-gray-900 dark:text-white">
                    {{ title }}
                </h3>
                <!-- 加载指示器 -->
                <span
                    v-if="isLoading"
                    class="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full"
                />
            </div>

            <!-- 操作按钮插槽 -->
            <div class="flex items-center gap-2">
                <slot name="actions" />
            </div>
        </div>

        <!-- 内容区域 -->
        <div class="p-6 text-gray-800 dark:text-gray-200">
            <!-- 加载状态 -->
            <div
                v-if="isLoading"
                class="flex flex-col items-center justify-center py-12 gap-4"
            >
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                <p class="text-gray-500 dark:text-gray-400 text-sm">
                    {{ loadingText }}
                </p>
            </div>

            <!-- 实际内容 -->
            <div v-else>
                <slot />
            </div>
        </div>
    </section>
</template>
