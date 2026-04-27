<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/task'
import {
    fetchBilibiliPages,
    lookupWorkspaceBySeries,
} from '@/api/workspace'
import type { BilibiliPage, BilibiliVideoMetaResponse } from '@/types'
import IconPlaylist from '~icons/material-symbols/playlist-play'
import IconClose from '~icons/material-symbols/close'

const props = defineProps<{
    bvid: string
    currentIndex: number
}>()

const router = useRouter()
const taskStore = useTaskStore()
const { url } = storeToRefs(taskStore)

const open = ref(false)
const meta = ref<BilibiliVideoMetaResponse | null>(null)
const loading = ref(false)
const switching = ref(false)

async function ensureMeta(): Promise<void> {
    if (meta.value && meta.value.bvid === props.bvid) return
    loading.value = true
    try {
        const data = await fetchBilibiliPages(`https://www.bilibili.com/video/${props.bvid}`)
        meta.value = data
    } finally {
        loading.value = false
    }
}

async function openDialog(): Promise<void> {
    open.value = true
    await ensureMeta()
}

function closeDialog(): void {
    if (switching.value) return
    open.value = false
}

async function selectPage(p: BilibiliPage): Promise<void> {
    if (p.page === props.currentIndex || switching.value) return
    switching.value = true
    try {
        const existingId = await lookupWorkspaceBySeries(props.bvid, p.page)
        if (existingId) {
            open.value = false
            await router.push({ name: 'workspace', params: { id: existingId } })
            return
        }

        // 未命中 → 用该 P 的 URL 创建新 workspace
        url.value = p.url
        const newId = await taskStore.submitUrl({
            overrideUrl: p.url,
            seriesBvid: props.bvid,
            seriesIndex: p.page,
        })
        if (newId) {
            open.value = false
            await router.push({ name: 'workspace', params: { id: newId } })
        }
    } finally {
        switching.value = false
    }
}

function formatDuration(seconds: number): string {
    if (!seconds || seconds <= 0) return ''
    const total = Math.round(seconds)
    const h = Math.floor(total / 3600)
    const m = Math.floor((total % 3600) / 60)
    const s = total % 60
    if (h > 0) {
        return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    }
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
</script>

<template>
    <div>
        <!-- 触发器按钮 -->
        <button
            type="button"
            class="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-dark-border-light rounded-lg bg-white dark:bg-dark-card hover:border-primary dark:hover:border-primary transition-colors cursor-pointer"
            @click="openDialog"
        >
            <IconPlaylist class="text-base text-primary" />
            <span>P{{ currentIndex }} · 切换分 P</span>
        </button>

        <!-- 弹层 -->
        <div
            v-if="open"
            class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 backdrop-blur-sm pt-20 px-4"
            @click.self="closeDialog"
        >
            <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl shadow-xl max-w-xl w-full max-h-[70vh] flex flex-col overflow-hidden">
                <!-- 标题 -->
                <div class="flex items-center gap-3 px-4 py-3 border-b border-gray-200 dark:border-dark-border">
                    <IconPlaylist class="text-lg text-primary shrink-0" />
                    <div class="flex-1 min-w-0">
                        <div class="text-sm font-medium text-gray-900 dark:text-white truncate">
                            {{ meta?.title || '加载中...' }}
                        </div>
                        <div
                            v-if="meta"
                            class="text-xs text-gray-500 dark:text-dark-text-muted"
                        >
                            共 {{ meta.pages.length }} 集 · 当前 P{{ currentIndex }}
                        </div>
                    </div>
                    <button
                        type="button"
                        class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 cursor-pointer"
                        :disabled="switching"
                        @click="closeDialog"
                    >
                        <IconClose class="text-lg" />
                    </button>
                </div>

                <!-- 列表 -->
                <div class="flex-1 overflow-y-auto divide-y divide-gray-100 dark:divide-dark-border">
                    <div
                        v-if="loading"
                        class="flex items-center justify-center gap-2 px-4 py-8 text-sm text-gray-500 dark:text-dark-text-muted"
                    >
                        <div class="animate-spin h-4 w-4 rounded-full border-2 border-gray-300 border-t-primary" />
                        <span>加载分 P 列表...</span>
                    </div>
                    <button
                        v-for="p in meta?.pages || []"
                        :key="p.page"
                        type="button"
                        class="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors cursor-pointer disabled:cursor-wait"
                        :class="p.page === currentIndex
                            ? 'bg-primary/10 dark:bg-primary/20 text-primary'
                            : 'hover:bg-gray-50 dark:hover:bg-dark-border text-gray-900 dark:text-white'"
                        :disabled="switching"
                        @click="selectPage(p)"
                    >
                        <span
                            class="text-xs font-mono w-10 shrink-0"
                            :class="p.page === currentIndex ? 'text-primary' : 'text-gray-400 dark:text-dark-text-muted'"
                        >
                            P{{ p.page }}
                        </span>
                        <span class="text-sm flex-1 truncate">{{ p.title }}</span>
                        <span
                            class="text-xs shrink-0"
                            :class="p.page === currentIndex ? 'text-primary' : 'text-gray-400 dark:text-dark-text-muted'"
                        >
                            {{ formatDuration(p.duration) }}
                        </span>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>
