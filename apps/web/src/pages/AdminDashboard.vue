<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getAdminHistory, getAdminStats } from '@/api/admin'
import type { AdminHistoryItem, AdminStatsResponse } from '@/types'

const LIMIT = 20

const loading = ref(true)
const error = ref('')
const stats = ref<AdminStatsResponse | null>(null)
const lastUpdated = ref('')

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

function stampNow() {
    const d = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    lastUpdated.value = `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadAll() {
    loading.value = true
    error.value = ''
    try {
        await Promise.all([loadStats(), loadHistory(offset.value)])
        stampNow()
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

// ---- 概览卡片 ----
const successRatePct = computed(() =>
    stats.value ? (stats.value.success_rate * 100).toFixed(1) : '0.0',
)
// 成功率用颜色编码健康度：≥90% 健康 / ≥70% 关注 / 更低告警
const successTone = computed(() => {
    const r = stats.value?.success_rate ?? 0
    if (r >= 0.9) return 'text-emerald-600'
    if (r >= 0.7) return 'text-signal'
    return 'text-red-600'
})

interface StatCard {
    eyebrow: string
    unit: string
    value: string
    sub?: string
    tone?: string
}
const cards = computed<StatCard[]>(() => {
    const s = stats.value
    if (!s) return []
    return [
        { eyebrow: '总浏览量', unit: 'PV', value: s.pv_total.toLocaleString() },
        { eyebrow: '独立访客', unit: 'UV', value: s.uv_total.toLocaleString() },
        {
            eyebrow: '转录总数',
            unit: 'JOBS',
            value: s.transcribe_total.toLocaleString(),
            sub: `成功 ${s.ready_count} · 失败 ${s.failed_count}`,
        },
        { eyebrow: '处理成功率', unit: '', value: `${successRatePct.value}%`, tone: successTone.value },
    ]
})

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
    if (s === 'ready') return 'bg-emerald-50 text-emerald-700 ring-emerald-600/20'
    if (s === 'failed') return 'bg-red-50 text-red-700 ring-red-600/20'
    return 'bg-surface-sunk text-ink-soft ring-line'
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
</script>

<template>
    <div class="min-h-screen bg-canvas font-body text-ink">
        <!-- 顶栏：品牌 + 控制台标识（内网运维页，无登录态/退出） -->
        <header class="border-b border-line bg-surface">
            <div class="mx-auto flex h-14 max-w-6xl items-center gap-2.5 px-4 sm:px-6">
                <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-ink">
                    <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
                        <rect x="2" y="6" width="2" height="4" rx="1" fill="#de8c2e" />
                        <rect x="6" y="2.5" width="2" height="11" rx="1" fill="#fff" />
                        <rect x="10" y="5" width="2" height="6" rx="1" fill="#fff" />
                    </svg>
                </span>
                <span class="font-title text-base font-bold tracking-tight">Gist</span>
                <span class="ml-0.5 rounded border border-line px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-faint">
                    控制台
                </span>
            </div>
        </header>

        <main class="mx-auto max-w-6xl px-4 py-8 sm:px-6">
            <!-- 页面标题 + 刷新 -->
            <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <h1 class="font-title text-2xl font-bold tracking-tight">运行概览</h1>
                    <p class="mt-1 text-sm text-ink-soft">浏览量 · 转录质量 · 处理耗时</p>
                </div>
                <div class="flex items-center gap-3">
                    <span v-if="lastUpdated" class="font-mono text-xs text-ink-faint">更新于 {{ lastUpdated }}</span>
                    <button
                        class="h-9 rounded-lg border border-line bg-surface px-4 text-sm font-medium text-ink-soft transition-colors hover:border-ink-faint hover:text-ink disabled:opacity-50"
                        :disabled="loading"
                        @click="loadAll"
                    >
                        {{ loading ? '加载中…' : '刷新' }}
                    </button>
                </div>
            </div>

            <!-- 错误条 -->
            <div
                v-if="error"
                class="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
                {{ error }}
            </div>

            <!-- 首屏加载（刷新时保留旧数据，不整屏闪烁） -->
            <div
                v-if="loading && !stats"
                class="py-24 text-center font-mono text-sm text-ink-faint"
            >
                加载中…
            </div>

            <template v-else>
                <!-- 概览卡片：mono 大数字是主角 -->
                <section v-if="stats" class="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
                    <div
                        v-for="c in cards"
                        :key="c.eyebrow"
                        class="rounded-xl border border-line bg-surface p-5"
                    >
                        <div class="flex items-baseline justify-between">
                            <p class="font-mono text-[11px] uppercase tracking-wider text-ink-faint">
                                {{ c.eyebrow }}
                            </p>
                            <span v-if="c.unit" class="font-mono text-[10px] tracking-wider text-ink-faint">
                                {{ c.unit }}
                            </span>
                        </div>
                        <p
                            class="mt-3 font-mono text-[2rem] font-semibold leading-none tracking-tight"
                            :class="c.tone ?? 'text-ink'"
                        >
                            {{ c.value }}
                        </p>
                        <p v-if="c.sub" class="mt-2 font-mono text-xs text-ink-faint">{{ c.sub }}</p>
                    </div>
                </section>

                <!-- 趋势 + 失败分布 -->
                <div class="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
                    <!-- PV/UV 趋势 -->
                    <section class="overflow-hidden rounded-xl border border-line bg-surface">
                        <div class="flex items-center justify-between border-b border-line px-5 py-3.5">
                            <h3 class="font-title text-sm font-semibold tracking-tight">近 14 天访问趋势</h3>
                            <div class="flex items-center gap-3 font-mono text-[11px] text-ink-faint">
                                <span class="flex items-center gap-1">
                                    <span class="inline-block h-2.5 w-2.5 rounded-sm bg-signal" />PV
                                </span>
                                <span class="flex items-center gap-1">
                                    <span class="inline-block h-2.5 w-2.5 rounded-sm bg-signal/35" />UV
                                </span>
                            </div>
                        </div>
                        <div class="p-5">
                            <div v-if="stats && stats.daily.length" class="flex h-40 items-end gap-1">
                                <div
                                    v-for="d in stats.daily"
                                    :key="d.date"
                                    class="flex h-full flex-1 flex-col items-center justify-end"
                                    :title="`${d.date} · PV ${d.pv} / UV ${d.uv}`"
                                >
                                    <div class="flex w-full flex-1 items-end justify-center gap-0.5">
                                        <div
                                            class="w-1.5 rounded-t bg-signal transition-all sm:w-2"
                                            :style="{ height: `${barPct(d.pv)}%` }"
                                        />
                                        <div
                                            class="w-1.5 rounded-t bg-signal/35 transition-all sm:w-2"
                                            :style="{ height: `${barPct(d.uv)}%` }"
                                        />
                                    </div>
                                    <span class="mt-1.5 font-mono text-[10px] text-ink-faint">{{ shortDate(d.date) }}</span>
                                </div>
                            </div>
                            <p v-else class="py-8 text-center text-sm text-ink-faint">暂无数据</p>
                        </div>
                    </section>

                    <!-- 失败原因分布 -->
                    <section class="overflow-hidden rounded-xl border border-line bg-surface">
                        <div class="border-b border-line px-5 py-3.5">
                            <h3 class="font-title text-sm font-semibold tracking-tight">失败原因分布</h3>
                        </div>
                        <div class="p-5">
                            <ul v-if="errorKindList.length" class="space-y-3.5">
                                <li
                                    v-for="item in errorKindList"
                                    :key="item.kind"
                                    class="grid grid-cols-[6rem_1fr_2.5rem] items-center gap-3 text-sm"
                                >
                                    <span class="truncate text-ink-soft">{{ errorKindLabel(item.kind) }}</span>
                                    <div class="h-2 overflow-hidden rounded-full bg-surface-sunk">
                                        <div class="h-full rounded-full bg-red-400" :style="{ width: `${item.pct}%` }" />
                                    </div>
                                    <span class="text-right font-mono text-ink">{{ item.count }}</span>
                                </li>
                            </ul>
                            <p v-else class="py-8 text-center text-sm text-ink-faint">近期没有失败任务</p>
                        </div>
                    </section>
                </div>

                <!-- 转录历史 -->
                <section class="overflow-hidden rounded-xl border border-line bg-surface">
                    <div class="flex items-center justify-between border-b border-line px-5 py-3.5">
                        <h3 class="font-title text-sm font-semibold tracking-tight">转录历史</h3>
                        <span class="font-mono text-xs text-ink-faint">{{ historyTotal }} 条</span>
                    </div>

                    <div class="overflow-x-auto">
                        <table class="w-full text-sm">
                            <thead>
                                <tr class="border-b border-line text-left font-mono text-[11px] uppercase tracking-wider text-ink-faint">
                                    <th class="px-5 py-2.5 font-medium">视频</th>
                                    <th class="px-4 py-2.5 font-medium">状态</th>
                                    <th class="whitespace-nowrap px-4 py-2.5 font-medium">完成时间</th>
                                    <th class="px-4 py-2.5 text-right font-medium">下载</th>
                                    <th class="px-4 py-2.5 text-right font-medium">转录</th>
                                    <th class="px-4 py-2.5 text-right font-medium">总耗时</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr
                                    v-for="item in history"
                                    :key="item.workspace_id"
                                    class="border-b border-line/60 transition-colors last:border-0 hover:bg-surface-sunk"
                                >
                                    <td class="max-w-xs px-5 py-3">
                                        <a
                                            :href="`/w/${item.workspace_id}`"
                                            class="block truncate font-medium text-ink transition-colors hover:text-signal"
                                            :title="item.title || item.url"
                                        >
                                            {{ item.title || '(无标题)' }}
                                        </a>
                                        <span class="font-mono text-xs text-ink-faint">{{ sourceHost(item.url) }}</span>
                                    </td>
                                    <td class="px-4 py-3">
                                        <span
                                            class="inline-block rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset"
                                            :class="statusBadgeClass(item.status)"
                                        >
                                            {{ statusLabel(item.status) }}
                                        </span>
                                        <span
                                            v-if="item.status === 'failed' && item.error_kind"
                                            class="mt-1 block text-xs text-ink-faint"
                                        >
                                            {{ errorKindLabel(item.error_kind) }}
                                        </span>
                                    </td>
                                    <td class="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink-soft">
                                        {{ formatDate(item.finished_at) }}
                                    </td>
                                    <td class="px-4 py-3 text-right font-mono text-ink-soft">{{ formatSeconds(item.timings.download) }}</td>
                                    <td class="px-4 py-3 text-right font-mono text-ink-soft">{{ formatSeconds(item.timings.stt_total) }}</td>
                                    <td class="px-4 py-3 text-right font-mono text-ink">{{ formatSeconds(item.timings.total) }}</td>
                                </tr>
                                <tr v-if="!history.length">
                                    <td colspan="6" class="px-5 py-12 text-center text-sm text-ink-faint">暂无转录记录</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <!-- 分页 -->
                    <div
                        v-if="historyTotal > 0"
                        class="flex items-center justify-between border-t border-line px-5 py-3.5"
                    >
                        <span class="font-mono text-xs text-ink-faint">第 {{ page }} / {{ totalPages }} 页</span>
                        <div class="flex items-center gap-2">
                            <button
                                class="h-8 rounded-lg border border-line px-3 text-sm text-ink-soft transition-colors hover:border-ink-faint hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
                                :disabled="!canPrev || historyLoading"
                                @click="prevPage"
                            >
                                上一页
                            </button>
                            <button
                                class="h-8 rounded-lg border border-line px-3 text-sm text-ink-soft transition-colors hover:border-ink-faint hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
                                :disabled="!canNext || historyLoading"
                                @click="nextPage"
                            >
                                下一页
                            </button>
                        </div>
                    </div>
                </section>
            </template>
        </main>
    </div>
</template>
