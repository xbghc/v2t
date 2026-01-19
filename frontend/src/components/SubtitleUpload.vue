<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTaskStore } from '@/stores/task'

const taskStore = useTaskStore()

const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

// 支持的文件类型
const acceptedTypes = ['.srt', '.txt', '.vtt', '.ass', '.ssa']

// 是否已上传文件
const hasFile = computed(() => taskStore.subtitleText.length > 0)

// 处理文件选择
const handleFileSelect = (event: Event) => {
    const target = event.target as HTMLInputElement
    const file = target.files?.[0]
    if (file) {
        processFile(file)
    }
}

// 处理拖放
const handleDrop = (event: DragEvent) => {
    event.preventDefault()
    isDragging.value = false

    const file = event.dataTransfer?.files?.[0]
    if (file) {
        processFile(file)
    }
}

// 处理文件
const processFile = async (file: File) => {
    // 检查文件类型
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!acceptedTypes.includes(ext)) {
        alert(`不支持的文件格式，请上传 ${acceptedTypes.join(', ')} 文件`)
        return
    }

    // 读取文件内容
    try {
        const text = await file.text()
        if (!text.trim()) {
            alert('文件内容为空')
            return
        }

        // 设置内容和标题
        taskStore.subtitleText = text
        // 使用文件名（去掉扩展名）作为默认标题
        taskStore.subtitleTitle = file.name.replace(/\.[^.]+$/, '')
    } catch (error) {
        console.error('读取文件失败:', error)
        alert('读取文件失败')
    }
}

// 点击选择文件
const triggerFileSelect = () => {
    fileInput.value?.click()
}

// 清除已选文件
const clearFile = () => {
    taskStore.subtitleText = ''
    taskStore.subtitleTitle = ''
    if (fileInput.value) {
        fileInput.value.value = ''
    }
}

// 拖拽事件
const handleDragOver = (event: DragEvent) => {
    event.preventDefault()
    isDragging.value = true
}

const handleDragLeave = () => {
    isDragging.value = false
}
</script>

<template>
    <div class="w-full max-w-input">
        <!-- 文件上传区域 -->
        <div
            v-if="!hasFile"
            class="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors duration-200"
            :class="[
                isDragging
                    ? 'border-primary bg-primary/5 dark:bg-primary/10'
                    : 'border-gray-300 dark:border-dark-border-light hover:border-primary dark:hover:border-primary'
            ]"
            @click="triggerFileSelect"
            @drop="handleDrop"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
        >
            <input
                ref="fileInput"
                type="file"
                :accept="acceptedTypes.join(',')"
                class="hidden"
                @change="handleFileSelect"
            >
            <span class="material-symbols-outlined text-4xl text-gray-400 dark:text-dark-text-muted mb-3">
                upload_file
            </span>
            <p class="text-sm text-gray-600 dark:text-gray-300 mb-1">
                拖放字幕文件到这里，或点击选择文件
            </p>
            <p class="text-xs text-gray-400 dark:text-dark-text-muted">
                支持 .srt, .txt, .vtt, .ass 格式
            </p>
        </div>

        <!-- 已上传文件显示 -->
        <div
            v-else
            class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border-light rounded-lg p-4"
        >
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-primary">description</span>
                    <span class="text-sm font-medium text-gray-900 dark:text-white truncate max-w-[200px]">
                        {{ taskStore.subtitleTitle || '未命名' }}
                    </span>
                </div>
                <button
                    type="button"
                    class="text-gray-400 hover:text-red-500 dark:text-dark-text-muted dark:hover:text-red-400 transition-colors"
                    title="清除文件"
                    @click="clearFile"
                >
                    <span class="material-symbols-outlined text-xl">close</span>
                </button>
            </div>

            <!-- 标题输入 -->
            <div class="mb-3">
                <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">标题</label>
                <input
                    v-model="taskStore.subtitleTitle"
                    type="text"
                    class="w-full text-sm rounded-lg border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card text-gray-900 dark:text-white px-3 py-2 placeholder:text-gray-400 dark:placeholder:text-dark-text-muted focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-colors"
                    placeholder="输入标题（可选）"
                >
            </div>

            <!-- 内容预览 -->
            <div>
                <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                    内容预览 ({{ taskStore.subtitleText.length }} 字符)
                </label>
                <div class="text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-dark-bg rounded p-2 max-h-24 overflow-y-auto whitespace-pre-wrap break-words">
                    {{ taskStore.subtitleText.slice(0, 500) }}{{ taskStore.subtitleText.length > 500 ? '...' : '' }}
                </div>
            </div>
        </div>
    </div>
</template>
