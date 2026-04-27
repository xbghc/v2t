<script setup lang="ts">
import { ref, watch } from 'vue'
import IconChevronRight from '~icons/material-symbols/chevron-right'
import IconPlaylist from '~icons/material-symbols/playlist-play'
import { fetchBilibiliPages } from '@/api/workspace'
import type { BilibiliPage, BilibiliVideoMetaResponse } from '@/types'

const props = defineProps<{
    url: string
}>()

const emit = defineEmits<{
    (e: 'select', page: BilibiliPage, bvid: string): void
}>()

const meta = ref<BilibiliVideoMetaResponse | null>(null)
const expanded = ref(false)
const loading = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null
let lastProbedUrl = ''

const containsBvid = (s: string): boolean => /BV[0-9A-Za-z]{10}/.test(s)

watch(
    () => props.url,
    (newUrl) => {
        const trimmed = newUrl?.trim() ?? ''

        // URL 不含 BV → 重置
        if (!trimmed || !containsBvid(trimmed)) {
            meta.value = null
            expanded.value = false
            lastProbedUrl = ''
            if (debounceTimer) clearTimeout(debounceTimer)
            return
        }

        // 同一 BV 不重复探测
        const bvMatch = trimmed.match(/BV[0-9A-Za-z]{10}/)
        if (bvMatch && lastProbedUrl === bvMatch[0]) return

        if (debounceTimer) clearTimeout(debounceTimer)
        debounceTimer = setTimeout(() => {
            void probe(trimmed)
        }, 500)
    },
    { immediate: true }
)

async function probe(url: string): Promise<void> {
    loading.value = true
    try {
        const data = await fetchBilibiliPages(url)
        if (data && data.pages.length >= 2) {
            meta.value = data
            lastProbedUrl = data.bvid
        } else {
            meta.value = null
            lastProbedUrl = ''
        }
        expanded.value = false
    } finally {
        loading.value = false
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

function handleSelect(page: BilibiliPage): void {
    if (!meta.value) return
    emit('select', page, meta.value.bvid)
}
</script>

<template>
    <div
        v-if="meta || loading"
        class="w-full max-w-input mt-3"
    >
        <!-- 折叠横条 -->
        <button
            v-if="meta"
            type="button"
            class="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-gray-300 dark:border-dark-border-light bg-white dark:bg-dark-card text-left hover:border-primary dark:hover:border-primary transition-colors cursor-pointer"
            @click="expanded = !expanded"
        >
            <IconPlaylist class="text-lg text-primary shrink-0" />
            <span class="text-sm text-gray-900 dark:text-white truncate flex-1">
                <span class="font-medium">检测到合集（{{ meta.pages.length }} 集）</span>
                <span class="text-gray-500 dark:text-gray-400">· {{ meta.title }}</span>
            </span>
            <IconChevronRight
                class="text-base text-gray-400 transition-transform duration-200 shrink-0"
                :class="{ 'rotate-90': expanded }"
            />
        </button>

        <!-- 探测中提示 -->
        <div
            v-else-if="loading"
            class="flex items-center gap-2 px-3 py-2.5 text-xs text-gray-400 dark:text-dark-text-muted"
        >
            <div class="animate-spin h-3 w-3 rounded-full border-2 border-gray-300 border-t-primary" />
            <span>检测视频信息...</span>
        </div>

        <!-- 分 P 列表 -->
        <div
            v-if="meta && expanded"
            class="mt-2 max-h-80 overflow-y-auto rounded-lg border border-gray-200 dark:border-dark-border-light bg-white dark:bg-dark-card divide-y divide-gray-100 dark:divide-dark-border"
        >
            <button
                v-for="p in meta.pages"
                :key="p.page"
                type="button"
                class="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-dark-border transition-colors cursor-pointer"
                @click="handleSelect(p)"
            >
                <span class="text-xs font-mono text-gray-400 dark:text-dark-text-muted w-10 shrink-0">
                    P{{ p.page }}
                </span>
                <span class="text-sm text-gray-900 dark:text-white flex-1 truncate">
                    {{ p.title }}
                </span>
                <span class="text-xs text-gray-400 dark:text-dark-text-muted shrink-0">
                    {{ formatDuration(p.duration) }}
                </span>
            </button>
        </div>
    </div>
</template>
