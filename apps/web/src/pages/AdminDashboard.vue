<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getAdminHistory, getAdminStats } from '@/api/admin'
import type { AdminHistoryItem, AdminStatsResponse } from '@/types'

const LIMIT = 20

const loading = ref(true)
const error = ref('')
const stats = ref<AdminStatsResponse | null>(null)

const history = ref<AdminHistoryItem[]>([])
const historyTotal = ref(0)
const historyLoading = ref(false)
const offset = ref(0)

async function loadStats() {
    stats.value = await getAdminStats(14)
}

async function loadHistory(newOffset: number) {
    historyLoading.value = true
    try {
        const res = await getAdminHistory(newOffset, LIMIT)
        history.value = res.items
        historyTotal.value = res.total
        offset.value = res.offset
    } finally {
        historyLoading.value = false
    }
}

async function loadAll() {
    loading.value = true
    error.value = ''
    try {
        await Promise.all([loadStats(), loadHistory(offset.value)])
    } catch (e) {
        error.value = (e as Error).message || '加载失败'
    } finally {
        loading.value = false
    }
}

onMounted(loadAll)

// ---- 趋势图 ----
const maxPv = computed(() =>
    Math.max(1, ...(stats.value?.daily.map((d) => d.pv) ?? [0])),
)

function barPct(v: number): number {
    return Math.min(100, (v / maxPv.value) * 100)
}

function shortDate(date: string): string {
    return date.slice(5) // YYYY-MM-DD → MM-DD
}

// ---- 失败原因分布 ----
const errorKindList = computed(() => {
    const ek = stats.value?.error_kind ?? {}
    const sum = Object.values(ek).reduce((a, b) => a + b, 0)
    return Object.entries(ek)
        .sort((a, b) => b[1] - a[1])
        .map(([kind, count]) => ({
            kind,
            count,
            pct: sum ? (count / sum) * 100 : 0,
        }))
})

// ---- 分页 ----
const page = computed(() => Math.floor(offset.value / LIMIT) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(historyTotal.value / LIMIT)))
const canPrev = computed(() => offset.value > 0)
const canNext = computed(() => offset.value + LIMIT < historyTotal.value)

function prevPage() {
    if (canPrev.value) loadHistory(Math.max(0, offset.value - LIMIT))
}
function nextPage() {
    if (canNext.value) loadHistory(offset.value + LIMIT)
}

// ---- 格式化 / 标签 ----
const ERROR_KIND_LABELS: Record<string, string> = {
    video_too_long: '视频过长',
    download_failed: '下载失败',
    transcribe_failed: '转录失败',
    unknown: '未知错误',
    '': '无分类',
}
function errorKindLabel(kind: string): string {
    return ERROR_KIND_LABELS[kind] ?? kind
}

const STATUS_LABELS: Record<string, string> = {
    ready: '成功',
    failed: '失败',
    processing: '处理中',
    pending: '等待',
}
function statusLabel(s: string): string {
    return STATUS_LABELS[s] ?? s
}
function statusBadgeClass(s: string): string {
    if (s === 'ready')
        return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
    if (s === 'failed')
        return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
    return 'bg-gray-100 text-gray-600 dark:bg-dark-border dark:text-gray-300'
}

function formatSeconds(s: number | undefined): string {
    if (!s || s < 0) return '–'
    if (s < 60) return `${s.toFixed(1)}s`
    const m = Math.floor(s / 60)
    return `${m}m${Math.round(s - m * 60)}s`
}

function formatDate(ts: number): string {
    if (!ts) return '–'
    const d = new Date(ts * 1000)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function sourceHost(url: string): string {
    try {
        return new URL(url).hostname.replace(/^www\./, '')
    } catch {
        return ''
    }
}

const successRatePct = computed(() =>
    stats.value ? (stats.value.success_rate * 100).toFixed(1) : '0.0',
)
</script>

<template>
    <div class="min-h-screen bg-gray-50 dark:bg-dark-bg text-gray-900 dark:text-white">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 py-8">
            <!-- 头部 -->
            <header class="flex items-center justify-between mb-6">
                <div>
                    <h1 class="text-2xl font-bold">后台管理</h1>
                    <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        浏览量 · 转录历史 · 处理质量
                    </p>
                </div>
                <button
                    class="flex items-center gap-2 h-10 px-4 rounded-lg bg-primary text-white font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                    :disabled="loading"
                    @click="loadAll"
                >
                    {{ loading ? '加载中…' : '刷新' }}
                </button>
            </header>

            <!-- 错误条 -->
            <div
                v-if="error"
                class="mb-6 px-4 py-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-sm"
            >
                {{ error }}
            </div>

            <!-- 初次加载 -->
            <div
                v-if="loading"
                class="py-20 text-center text-gray-400 dark:text-gray-500"
            >
                加载中…
            </div>

            <template v-else>
                <!-- 统计卡片 -->
                <section
                    v-if="stats"
                    class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6"
                >
                    <div class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-5">
                        <p class="text-sm text-gray-500 dark:text-gray-400">总浏览量 PV</p>
                        <p class="text-3xl font-bold mt-2">{{ stats.pv_total.toLocaleString() }}</p>
                    </div>
                    <div class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-5">
                        <p class="text-sm text-gray-500 dark:text-gray-400">独立访客 UV</p>
                        <p class="text-3xl font-bold mt-2">{{ stats.uv_total.toLocaleString() }}</p>
                    </div>
                    <div class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-5">
                        <p class="text-sm text-gray-500 dark:text-gray-400">转录总数</p>
                        <p class="text-3xl font-bold mt-2">{{ stats.transcribe_total.toLocaleString() }}</p>
                        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
                            成功 {{ stats.ready_count }} · 失败 {{ stats.failed_count }}
                        </p>
                    </div>
                    <div class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-5">
                        <p class="text-sm text-gray-500 dark:text-gray-400">处理成功率</p>
                        <p class="text-3xl font-bold mt-2">{{ successRatePct }}%</p>
                    </div>
                </section>

                <!-- 趋势 + 失败分布 -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                    <!-- PV/UV 趋势 -->
                    <section class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border overflow-hidden">
                        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-bg">
                            <h3 class="text-base font-semibold">近 14 天访问趋势</h3>
                            <div class="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                                <span class="flex items-center gap-1">
                                    <span class="inline-block w-2.5 h-2.5 rounded-sm bg-primary" />PV
                                </span>
                                <span class="flex items-center gap-1">
                                    <span class="inline-block w-2.5 h-2.5 rounded-sm bg-primary/40" />UV
                                </span>
                            </div>
                        </div>
                        <div class="p-6">
                            <div
                                v-if="stats && stats.daily.length"
                                class="flex items-end gap-1 h-40"
                            >
                                <div
                                    v-for="d in stats.daily"
                                    :key="d.date"
                                    class="flex-1 flex flex-col items-center justify-end h-full"
                                    :title="`${d.date} PV ${d.pv} / UV ${d.uv}`"
                                >
                                    <div class="flex items-end justify-center gap-0.5 w-full flex-1">
                                        <div
                                            class="w-1.5 sm:w-2 bg-primary rounded-t transition-all"
                                            :style="{ height: `${barPct(d.pv)}%` }"
                                        />
                                        <div
                                            class="w-1.5 sm:w-2 bg-primary/40 rounded-t transition-all"
                                            :style="{ height: `${barPct(d.uv)}%` }"
                                        />
                                    </div>
                                    <span class="mt-1 text-[10px] text-gray-400 dark:text-gray-500 whitespace-nowrap">
                                        {{ shortDate(d.date) }}
                                    </span>
                                </div>
                            </div>
                            <p v-else class="text-sm text-gray-400 py-8 text-center">暂无数据</p>
                        </div>
                    </section>

                    <!-- 失败原因分布 -->
                    <section class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border overflow-hidden">
                        <div class="px-6 py-4 border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-bg">
                            <h3 class="text-base font-semibold">失败原因分布</h3>
                        </div>
                        <div class="p-6">
                            <ul v-if="errorKindList.length" class="space-y-3">
                                <li
                                    v-for="item in errorKindList"
                                    :key="item.kind"
                                    class="grid grid-cols-[6rem_1fr_2.5rem] items-center gap-3 text-sm"
                                >
                                    <span class="text-gray-600 dark:text-gray-400 truncate">
                                        {{ errorKindLabel(item.kind) }}
                                    </span>
                                    <div class="h-2 bg-gray-100 dark:bg-dark-border rounded-full overflow-hidden">
                                        <div
                                            class="h-full bg-red-500/80"
                                            :style="{ width: `${item.pct}%` }"
                                        />
                                    </div>
                                    <span class="text-right font-mono">{{ item.count }}</span>
                                </li>
                            </ul>
                            <p v-else class="text-sm text-gray-400 py-8 text-center">暂无失败记录 🎉</p>
                        </div>
                    </section>
                </div>

                <!-- 转录历史 -->
                <section class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border overflow-hidden">
                    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-bg">
                        <h3 class="text-base font-semibold">转录历史</h3>
                        <span class="text-sm text-gray-500 dark:text-gray-400">共 {{ historyTotal }} 条</span>
                    </div>

                    <div class="overflow-x-auto">
                        <table class="w-full text-sm">
                            <thead>
                                <tr class="border-b border-gray-200 dark:border-dark-border text-left text-gray-500 dark:text-gray-400">
                                    <th class="px-6 py-3 font-medium">视频</th>
                                    <th class="px-4 py-3 font-medium">状态</th>
                                    <th class="px-4 py-3 font-medium whitespace-nowrap">完成时间</th>
                                    <th class="px-4 py-3 font-medium text-right whitespace-nowrap">下载</th>
                                    <th class="px-4 py-3 font-medium text-right whitespace-nowrap">转录</th>
                                    <th class="px-4 py-3 font-medium text-right whitespace-nowrap">总耗时</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr
                                    v-for="item in history"
                                    :key="item.workspace_id"
                                    class="border-b border-gray-100 dark:border-dark-border/60 hover:bg-gray-50 dark:hover:bg-dark-bg/50"
                                >
                                    <td class="px-6 py-3 max-w-xs">
                                        <a
                                            :href="`/w/${item.workspace_id}`"
                                            class="font-medium text-gray-900 dark:text-white hover:text-primary truncate block"
                                            :title="item.title || item.url"
                                        >
                                            {{ item.title || '(无标题)' }}
                                        </a>
                                        <span class="text-xs text-gray-400 dark:text-gray-500">
                                            {{ sourceHost(item.url) }}
                                        </span>
                                    </td>
                                    <td class="px-4 py-3">
                                        <span
                                            class="inline-block px-2 py-0.5 rounded text-xs font-medium"
                                            :class="statusBadgeClass(item.status)"
                                        >
                                            {{ statusLabel(item.status) }}
                                        </span>
                                        <span
                                            v-if="item.status === 'failed' && item.error_kind"
                                            class="block text-xs text-gray-400 mt-1"
                                        >
                                            {{ errorKindLabel(item.error_kind) }}
                                        </span>
                                    </td>
                                    <td class="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                                        {{ formatDate(item.finished_at) }}
                                    </td>
                                    <td class="px-4 py-3 text-right font-mono text-gray-600 dark:text-gray-300">
                                        {{ formatSeconds(item.timings.download) }}
                                    </td>
                                    <td class="px-4 py-3 text-right font-mono text-gray-600 dark:text-gray-300">
                                        {{ formatSeconds(item.timings.stt_total) }}
                                    </td>
                                    <td class="px-4 py-3 text-right font-mono text-gray-700 dark:text-gray-200">
                                        {{ formatSeconds(item.timings.total) }}
                                    </td>
                                </tr>
                                <tr v-if="!history.length">
                                    <td colspan="6" class="px-6 py-12 text-center text-gray-400">
                                        暂无转录记录
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <!-- 分页 -->
                    <div
                        v-if="historyTotal > 0"
                        class="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-dark-border"
                    >
                        <span class="text-sm text-gray-500 dark:text-gray-400">
                            第 {{ page }} / {{ totalPages }} 页
                        </span>
                        <div class="flex items-center gap-2">
                            <button
                                class="h-9 px-3 rounded-lg border border-gray-200 dark:border-dark-border text-sm hover:bg-gray-50 dark:hover:bg-dark-bg disabled:opacity-40 disabled:cursor-not-allowed"
                                :disabled="!canPrev || historyLoading"
                                @click="prevPage"
                            >
                                上一页
                            </button>
                            <button
                                class="h-9 px-3 rounded-lg border border-gray-200 dark:border-dark-border text-sm hover:bg-gray-50 dark:hover:bg-dark-bg disabled:opacity-40 disabled:cursor-not-allowed"
                                :disabled="!canNext || historyLoading"
                                @click="nextPage"
                            >
                                下一页
                            </button>
                        </div>
                    </div>
                </section>
            </template>
        </div>
    </div>
</template>
