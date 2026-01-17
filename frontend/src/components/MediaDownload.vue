<script setup lang="ts">
import { computed } from 'vue'
import type { MediaType } from '@/types'

interface Props {
    type: MediaType
    available?: boolean
    isProcessing?: boolean
    downloadUrl?: string
}

const props = withDefaults(defineProps<Props>(), {
    available: false,
    isProcessing: false,
    downloadUrl: ''
})

const icon = computed<string>(() => {
    if (props.type === 'video') {
        return props.available ? 'videocam' : (props.isProcessing ? 'hourglass_empty' : 'videocam_off')
    }
    if (props.type === 'podcast') {
        return props.available ? 'podcasts' : (props.isProcessing ? 'hourglass_empty' : 'podcasts')
    }
    return props.available ? 'audiotrack' : (props.isProcessing ? 'hourglass_empty' : 'music_off')
})

const label = computed<string>(() => {
    if (props.type === 'video') {
        if (props.available) return '下载视频'
        return props.isProcessing ? '下载中...' : '视频不可用'
    }
    if (props.type === 'podcast') {
        if (props.available) return '下载播客音频'
        return props.isProcessing ? '合成中...' : '播客音频不可用'
    }
    if (props.available) return '下载音频'
    return props.isProcessing ? '转录中...' : '音频不可用'
})

const showPulse = computed<boolean>(() => !props.available && props.isProcessing)
</script>

<template>
    <a
        v-if="available"
        :href="downloadUrl"
        class="flex w-full min-w-btn max-w-input cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-gray-200 dark:bg-dark-border text-gray-900 dark:text-white gap-2 text-sm font-medium leading-normal hover:bg-gray-300 dark:hover:bg-dark-border-light transition-colors"
    >
        <span class="material-symbols-outlined text-lg">{{ icon }}</span>
        <span class="truncate">{{ label }}</span>
    </a>
    <button
        v-else
        disabled
        class="flex w-full min-w-btn max-w-input items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-gray-100 dark:bg-dark-card text-gray-400 dark:text-gray-600 gap-2 text-sm font-medium leading-normal cursor-not-allowed"
    >
        <span
            class="material-symbols-outlined text-lg"
            :class="{ 'animate-pulse': showPulse }"
        >{{ icon }}</span>
        <span class="truncate">{{ label }}</span>
    </button>
</template>
