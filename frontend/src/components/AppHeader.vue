<script setup lang="ts">
import AppLogo from './AppLogo.vue'
import type { HeaderVariant } from '@/types'

interface Props {
    showNewButton?: boolean
    variant?: HeaderVariant
}

withDefaults(defineProps<Props>(), {
    showNewButton: false,
    variant: 'default'
})

defineEmits<{
    'new-task': []
}>()
</script>

<template>
    <header
        class="flex items-center justify-between whitespace-nowrap border-b border-solid border-gray-200 dark:border-b-dark-border py-3"
        :class="variant === 'result' ? 'px-6 sm:px-10 lg:px-20 bg-white dark:bg-dark-bg' : 'px-4 sm:px-6 lg:px-10'"
    >
        <div class="flex items-center gap-4 text-gray-800 dark:text-white">
            <AppLogo :size="variant === 'result' ? '6' : '5'" />
            <h2 class="text-lg font-bold leading-tight tracking-tight-sm text-gray-900 dark:text-white">
                V2T 视频转文字
            </h2>
        </div>
        <button
            v-if="showNewButton"
            class="flex min-w-btn max-w-input cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold leading-normal tracking-wide-sm hover:bg-primary/90 transition-colors"
            @click="$emit('new-task')"
        >
            <span class="truncate">新建转换</span>
        </button>
    </header>
</template>
