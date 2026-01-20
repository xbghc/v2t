<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'

interface Props {
    src: string
    title?: string
    available?: boolean
    isProcessing?: boolean
}

const props = withDefaults(defineProps<Props>(), {
    title: '音频',
    available: false,
    isProcessing: false
})

const audioRef = ref<HTMLAudioElement | null>(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)

const progress = computed(() => {
    if (duration.value === 0) return 0
    return (currentTime.value / duration.value) * 100
})

const formatTime = (time: number): string => {
    if (isNaN(time) || !isFinite(time)) return '0:00'
    const minutes = Math.floor(time / 60)
    const seconds = Math.floor(time % 60)
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const togglePlay = () => {
    if (!audioRef.value || !props.available) return
    if (isPlaying.value) {
        audioRef.value.pause()
    } else {
        audioRef.value.play()
    }
}

const handleTimeUpdate = () => {
    if (audioRef.value) {
        currentTime.value = audioRef.value.currentTime
    }
}

const handleLoadedMetadata = () => {
    if (audioRef.value) {
        duration.value = audioRef.value.duration
    }
}

const handlePlay = () => {
    isPlaying.value = true
}

const handlePause = () => {
    isPlaying.value = false
}

const handleEnded = () => {
    isPlaying.value = false
    currentTime.value = 0
}

const seekTo = (event: MouseEvent) => {
    if (!audioRef.value || !props.available) return
    const target = event.currentTarget as HTMLElement
    const rect = target.getBoundingClientRect()
    const percent = (event.clientX - rect.left) / rect.width
    const newTime = percent * duration.value
    audioRef.value.currentTime = newTime
    currentTime.value = newTime
}

const skip = (seconds: number) => {
    if (!audioRef.value || !props.available) return
    const newTime = Math.max(0, Math.min(duration.value, audioRef.value.currentTime + seconds))
    audioRef.value.currentTime = newTime
    currentTime.value = newTime
}

onUnmounted(() => {
    if (audioRef.value) {
        audioRef.value.pause()
    }
})
</script>

<template>
    <div class="flex flex-col gap-4">
        <!-- 处理中状态 -->
        <div
            v-if="!available && isProcessing"
            class="flex flex-col items-center justify-center py-12 bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-900/20 dark:to-cyan-900/20 rounded-lg"
        >
            <span class="material-symbols-outlined text-4xl text-blue-400 dark:text-blue-500 mb-3 animate-pulse">
                downloading
            </span>
            <span class="text-sm text-gray-500 dark:text-gray-400">正在处理音频...</span>
        </div>

        <!-- 不可用状态 -->
        <div
            v-else-if="!available && !isProcessing"
            class="flex flex-col items-center justify-center py-12 bg-gray-100 dark:bg-dark-bg rounded-lg"
        >
            <span class="material-symbols-outlined text-4xl text-gray-400 dark:text-gray-600 mb-3">
                music_off
            </span>
            <span class="text-sm text-gray-500 dark:text-gray-400">音频不可用</span>
        </div>

        <!-- 音频播放器 -->
        <template v-else>
            <div class="p-6 bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-900/20 dark:to-cyan-900/20 rounded-xl">
                <audio
                    ref="audioRef"
                    :src="src"
                    preload="metadata"
                    @timeupdate="handleTimeUpdate"
                    @loadedmetadata="handleLoadedMetadata"
                    @play="handlePlay"
                    @pause="handlePause"
                    @ended="handleEnded"
                />

                <!-- 控制按钮 -->
                <div class="flex items-center justify-center gap-4 mb-4">
                    <!-- 后退 10s -->
                    <button
                        class="flex items-center justify-center w-9 h-9 rounded-full text-gray-600 dark:text-gray-400 hover:bg-blue-100 dark:hover:bg-blue-800/30 transition-colors"
                        title="后退 10 秒"
                        @click="skip(-10)"
                    >
                        <span class="material-symbols-outlined text-xl">replay_10</span>
                    </button>

                    <!-- 播放/暂停 -->
                    <button
                        class="flex items-center justify-center w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg transition-colors"
                        @click="togglePlay"
                    >
                        <span class="material-symbols-outlined text-3xl">
                            {{ isPlaying ? 'pause' : 'play_arrow' }}
                        </span>
                    </button>

                    <!-- 快进 10s -->
                    <button
                        class="flex items-center justify-center w-9 h-9 rounded-full text-gray-600 dark:text-gray-400 hover:bg-blue-100 dark:hover:bg-blue-800/30 transition-colors"
                        title="快进 10 秒"
                        @click="skip(10)"
                    >
                        <span class="material-symbols-outlined text-xl">forward_10</span>
                    </button>
                </div>

                <!-- 进度条 -->
                <div class="flex items-center gap-3">
                    <span class="text-xs text-gray-500 dark:text-gray-400 w-10 text-right font-mono">
                        {{ formatTime(currentTime) }}
                    </span>
                    <div
                        class="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full cursor-pointer overflow-hidden"
                        @click="seekTo"
                    >
                        <div
                            class="h-full bg-blue-600 rounded-full transition-all duration-100"
                            :style="{ width: `${progress}%` }"
                        />
                    </div>
                    <span class="text-xs text-gray-500 dark:text-gray-400 w-10 font-mono">
                        {{ formatTime(duration) }}
                    </span>
                </div>
            </div>

            <!-- 下载按钮 -->
            <a
                :href="src"
                download
                class="flex items-center justify-center gap-2 py-3 rounded-lg bg-gray-100 dark:bg-dark-border hover:bg-gray-200 dark:hover:bg-dark-border-light text-gray-700 dark:text-gray-300 transition-colors"
            >
                <span class="material-symbols-outlined text-lg">download</span>
                <span>下载音频</span>
            </a>
        </template>
    </div>
</template>
