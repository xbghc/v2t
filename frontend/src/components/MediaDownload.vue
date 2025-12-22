<script setup>
import { computed } from 'vue'

const props = defineProps({
    type: {
        type: String,
        required: true,
        validator: (value) => ['video', 'audio'].includes(value)
    },
    available: {
        type: Boolean,
        default: false
    },
    isProcessing: {
        type: Boolean,
        default: false
    },
    downloadUrl: {
        type: String,
        default: ''
    }
})

const icon = computed(() => {
    if (props.type === 'video') {
        return props.available ? 'videocam' : (props.isProcessing ? 'hourglass_empty' : 'videocam_off')
    }
    return props.available ? 'audiotrack' : (props.isProcessing ? 'hourglass_empty' : 'music_off')
})

const label = computed(() => {
    if (props.type === 'video') {
        if (props.available) return '下载视频'
        return props.isProcessing ? '下载中...' : '视频不可用'
    }
    if (props.available) return '下载音频'
    return props.isProcessing ? '转录中...' : '音频不可用'
})

const showPulse = computed(() => !props.available && props.isProcessing)
</script>

<template>
    <a
        v-if="available"
        :href="downloadUrl"
        class="flex w-full min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-gray-200 dark:bg-[#282e39] text-gray-900 dark:text-white gap-2 text-sm font-medium leading-normal hover:bg-gray-300 dark:hover:bg-[#3b4354] transition-colors"
    >
        <span class="material-symbols-outlined text-lg">{{ icon }}</span>
        <span class="truncate">{{ label }}</span>
    </a>
    <button
        v-else
        disabled
        class="flex w-full min-w-[84px] max-w-[480px] items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-gray-100 dark:bg-[#1c1f27] text-gray-400 dark:text-gray-600 gap-2 text-sm font-medium leading-normal cursor-not-allowed"
    >
        <span class="material-symbols-outlined text-lg" :class="{ 'animate-pulse': showPulse }">{{ icon }}</span>
        <span class="truncate">{{ label }}</span>
    </button>
</template>
