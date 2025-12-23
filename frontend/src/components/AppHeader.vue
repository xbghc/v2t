<script setup>
import AppLogo from './AppLogo.vue'

defineProps({
    showNewButton: {
        type: Boolean,
        default: false
    },
    variant: {
        type: String,
        default: 'default' // 'default' | 'result'
    }
})

defineEmits(['new-task'])
</script>

<template>
    <header
        class="flex items-center justify-between whitespace-nowrap border-b border-solid border-gray-200 dark:border-b-dark-border py-3"
        :class="variant === 'result' ? 'px-6 sm:px-10 lg:px-20 bg-white dark:bg-dark-bg' : 'px-4 sm:px-6 lg:px-10'"
    >
        <div class="flex items-center gap-4 text-gray-800 dark:text-white">
            <AppLogo :size="variant === 'result' ? '6' : '5'" />
            <h2 class="text-lg font-bold leading-tight tracking-[-0.015em] text-gray-900 dark:text-white">V2T 视频转文字</h2>
        </div>
        <button
            v-if="showNewButton"
            @click="$emit('new-task')"
            class="flex min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold leading-normal tracking-[0.015em] hover:bg-primary/90 transition-colors"
        >
            <span class="truncate">新建转换</span>
        </button>
    </header>
</template>
