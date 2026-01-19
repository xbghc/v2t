<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'

interface Props {
    src: string
    available?: boolean
    isProcessing?: boolean
    error?: string
}

const props = withDefaults(defineProps<Props>(), {
    available: false,
    isProcessing: false,
    error: ''
})

const audioRef = ref<HTMLAudioElement | null>(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const isDragging = ref(false)

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
    if (audioRef.value && !isDragging.value) {
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
    <div class="flex flex-col gap-3 p-4 bg-gradient-to-br from-purple-50 to-indigo-50 dark:from-purple-900/20 dark:to-indigo-900/20 rounded-xl border border-purple-100 dark:border-purple-800/30">
        <!-- Header -->
        <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-purple-600 dark:text-purple-400">podcasts</span>
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">播客音频</span>
        </div>

        <!-- Processing State -->
        <div
            v-if="!available && isProcessing"
            class="flex items-center justify-center gap-2 py-4"
        >
            <span class="material-symbols-outlined text-purple-500 animate-pulse">hourglass_empty</span>
            <span class="text-sm text-gray-500 dark:text-gray-400">正在合成音频...</span>
        </div>

        <!-- Unavailable State -->
        <div
            v-else-if="!available && !isProcessing"
            class="flex items-center justify-center gap-2 py-4"
        >
            <span class="material-symbols-outlined text-gray-400 dark:text-gray-600">podcasts</span>
            <span class="text-sm text-gray-400 dark:text-gray-600">{{ error || '播客音频不可用' }}</span>
        </div>

        <!-- Player -->
        <template v-else>
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

            <!-- Controls -->
            <div class="flex items-center justify-center gap-4">
                <!-- Rewind 10s -->
                <button
                    class="flex items-center justify-center w-9 h-9 rounded-full text-gray-600 dark:text-gray-400 hover:bg-purple-100 dark:hover:bg-purple-800/30 transition-colors"
                    title="后退 10 秒"
                    @click="skip(-10)"
                >
                    <span class="material-symbols-outlined text-xl">replay_10</span>
                </button>

                <!-- Play/Pause -->
                <button
                    class="flex items-center justify-center w-12 h-12 rounded-full bg-purple-600 hover:bg-purple-700 text-white shadow-lg transition-colors"
                    @click="togglePlay"
                >
                    <span class="material-symbols-outlined text-2xl">
                        {{ isPlaying ? 'pause' : 'play_arrow' }}
                    </span>
                </button>

                <!-- Forward 10s -->
                <button
                    class="flex items-center justify-center w-9 h-9 rounded-full text-gray-600 dark:text-gray-400 hover:bg-purple-100 dark:hover:bg-purple-800/30 transition-colors"
                    title="快进 10 秒"
                    @click="skip(10)"
                >
                    <span class="material-symbols-outlined text-xl">forward_10</span>
                </button>
            </div>

            <!-- Progress Bar -->
            <div class="flex items-center gap-3">
                <span class="text-xs text-gray-500 dark:text-gray-400 w-10 text-right font-mono">
                    {{ formatTime(currentTime) }}
                </span>
                <div
                    class="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full cursor-pointer overflow-hidden"
                    @click="seekTo"
                >
                    <div
                        class="h-full bg-purple-600 rounded-full transition-all duration-100"
                        :style="{ width: `${progress}%` }"
                    />
                </div>
                <span class="text-xs text-gray-500 dark:text-gray-400 w-10 font-mono">
                    {{ formatTime(duration) }}
                </span>
            </div>

            <!-- Download Link -->
            <a
                :href="src"
                class="flex items-center justify-center gap-2 mt-1 py-2 text-sm text-purple-600 dark:text-purple-400 hover:text-purple-700 dark:hover:text-purple-300 transition-colors"
            >
                <span class="material-symbols-outlined text-lg">download</span>
                <span>下载音频</span>
            </a>
        </template>
    </div>
</template>
