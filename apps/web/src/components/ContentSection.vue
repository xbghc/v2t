<script setup lang="ts">
import type { Component } from 'vue'

interface Props {
    id: string
    title: string
    icon: Component
    isVisible?: boolean
    isLoading?: boolean
    loadingText?: string
}

withDefaults(defineProps<Props>(), {
    isVisible: true,
    isLoading: false,
    loadingText: '加载中...',
})
</script>

<template>
    <section
        v-show="isVisible"
        :id="`section-${id}`"
        class="scroll-mt-20 overflow-hidden rounded-2xl border border-line bg-surface transition-all duration-300"
    >
        <!-- 标题栏 -->
        <div class="flex items-center justify-between border-b border-line bg-surface-sunk px-6 py-4">
            <div class="flex items-center gap-3">
                <component :is="icon" class="text-xl text-signal" />
                <h3 class="font-title text-base font-semibold text-ink">
                    {{ title }}
                </h3>
                <span
                    v-if="isLoading"
                    class="h-4 w-4 animate-spin rounded-full border-2 border-signal border-t-transparent"
                />
            </div>
            <div class="flex items-center gap-2">
                <slot name="actions" />
            </div>
        </div>

        <!-- 内容区域 -->
        <div class="p-6 text-ink">
            <div
                v-if="isLoading"
                class="flex flex-col items-center justify-center gap-4 py-12"
            >
                <div class="h-8 w-8 animate-spin rounded-full border-b-2 border-signal" />
                <p class="text-sm text-ink-soft">{{ loadingText }}</p>
            </div>
            <div v-else>
                <slot />
            </div>
        </div>
    </section>
</template>
