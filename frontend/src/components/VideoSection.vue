<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
    src: string
    title?: string
    available?: boolean
    isProcessing?: boolean
}

const props = withDefaults(defineProps<Props>(), {
    title: '视频',
    available: false,
    isProcessing: false
})

const videoRef = ref<HTMLVideoElement | null>(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const isFullscreen = ref(false)

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
    if (!videoRef.value || !props.available) return
    if (isPlaying.value) {
        videoRef.value.pause()
    } else {
        videoRef.value.play()
    }
}

const handleTimeUpdate = () => {
    if (videoRef.value) {
        currentTime.value = videoRef.value.currentTime
    }
}

const handleLoadedMetadata = () => {
    if (videoRef.value) {
        duration.value = videoRef.value.duration
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
    if (!videoRef.value || !props.available) return
    const target = event.currentTarget as HTMLElement
    const rect = target.getBoundingClientRect()
    const percent = (event.clientX - rect.left) / rect.width
    const newTime = percent * duration.value
    videoRef.value.currentTime = newTime
    currentTime.value = newTime
}

const toggleFullscreen = () => {
    if (!videoRef.value) return
    if (!document.fullscreenElement) {
        videoRef.value.requestFullscreen()
        isFullscreen.value = true
    } else {
        document.exitFullscreen()
        isFullscreen.value = false
    }
}

const skip = (seconds: number) => {
    if (!videoRef.value || !props.available) return
    const newTime = Math.max(0, Math.min(duration.value, videoRef.value.currentTime + seconds))
    videoRef.value.currentTime = newTime
    currentTime.value = newTime
}
</script>

<template>
    <div class="flex flex-col gap-4">
        <!-- 处理中状态 -->
        <div
            v-if="!available && isProcessing"
            class="flex flex-col items-center justify-center py-12 bg-gray-100 dark:bg-dark-bg rounded-lg"
        >
            <span class="material-symbols-outlined text-4xl text-gray-400 dark:text-gray-600 mb-3 animate-pulse">
                downloading
            </span>
            <span class="text-sm text-gray-500 dark:text-gray-400">正在下载视频...</span>
        </div>

        <!-- 不可用状态 -->
        <div
            v-else-if="!available && !isProcessing"
            class="flex flex-col items-center justify-center py-12 bg-gray-100 dark:bg-dark-bg rounded-lg"
        >
            <span class="material-symbols-outlined text-4xl text-gray-400 dark:text-gray-600 mb-3">
                videocam_off
            </span>
            <span class="text-sm text-gray-500 dark:text-gray-400">视频不可用</span>
        </div>

        <!-- 视频播放器 -->
        <template v-else>
            <div class="relative bg-black rounded-lg overflow-hidden">
                <video
                    ref="videoRef"
                    :src="src"
                    class="w-full aspect-video"
                    preload="metadata"
                    @timeupdate="handleTimeUpdate"
                    @loadedmetadata="handleLoadedMetadata"
                    @play="handlePlay"
                    @pause="handlePause"
                    @ended="handleEnded"
                    @click="togglePlay"
                />

                <!-- 播放按钮覆盖层 -->
                <div
                    v-if="!isPlaying"
                    class="absolute inset-0 flex items-center justify-center bg-black/30 cursor-pointer"
                    @click="togglePlay"
                >
                    <div class="w-16 h-16 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
                        <span class="material-symbols-outlined text-4xl text-gray-800 ml-1">play_arrow</span>
                    </div>
                </div>
            </div>

            <!-- 控制栏 -->
            <div class="flex flex-col gap-2">
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
                            class="h-full bg-primary rounded-full transition-all duration-100"
                            :style="{ width: `${progress}%` }"
                        />
                    </div>
                    <span class="text-xs text-gray-500 dark:text-gray-400 w-10 font-mono">
                        {{ formatTime(duration) }}
                    </span>
                </div>

                <!-- 控制按钮 -->
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <!-- 后退 10s -->
                        <button
                            class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-border transition-colors"
                            title="后退 10 秒"
                            @click="skip(-10)"
                        >
                            <span class="material-symbols-outlined text-gray-600 dark:text-gray-400">replay_10</span>
                        </button>

                        <!-- 播放/暂停 -->
                        <button
                            class="p-2 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors"
                            @click="togglePlay"
                        >
                            <span class="material-symbols-outlined">
                                {{ isPlaying ? 'pause' : 'play_arrow' }}
                            </span>
                        </button>

                        <!-- 快进 10s -->
                        <button
                            class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-border transition-colors"
                            title="快进 10 秒"
                            @click="skip(10)"
                        >
                            <span class="material-symbols-outlined text-gray-600 dark:text-gray-400">forward_10</span>
                        </button>
                    </div>

                    <div class="flex items-center gap-2">
                        <!-- 全屏 -->
                        <button
                            class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-border transition-colors"
                            title="全屏"
                            @click="toggleFullscreen"
                        >
                            <span class="material-symbols-outlined text-gray-600 dark:text-gray-400">
                                {{ isFullscreen ? 'fullscreen_exit' : 'fullscreen' }}
                            </span>
                        </button>

                        <!-- 下载 -->
                        <a
                            :href="src"
                            download
                            class="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-100 dark:bg-dark-border hover:bg-gray-200 dark:hover:bg-dark-border-light text-gray-700 dark:text-gray-300 text-sm transition-colors"
                        >
                            <span class="material-symbols-outlined text-lg">download</span>
                            <span>下载视频</span>
                        </a>
                    </div>
                </div>
            </div>
        </template>
    </div>
</template>
