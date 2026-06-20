<script setup lang="ts">
import { computed } from 'vue'

interface Props {
    timings: Record<string, number>
    isVisible?: boolean
}

const props = withDefaults(defineProps<Props>(), { isVisible: true })

interface Row {
    key: string
    label: string
    seconds: number
    pct: number
}

const STAGE_LABELS: Record<string, string> = {
    download: '下载',
    vad_first_cut: '首片切出',
    stt_first_segment: '首段转录',
    stt_total: '全部转录',
}

const STAGE_ORDER = ['download', 'vad_first_cut', 'stt_first_segment', 'stt_total']

function formatSeconds(s: number): string {
    if (s < 0) return '–'
    if (s < 1) return `${(s * 1000).toFixed(0)}ms`
    if (s < 60) return `${s.toFixed(2)}s`
    const m = Math.floor(s / 60)
    const rest = s - m * 60
    return `${m}m ${rest.toFixed(1)}s`
}

const audioDuration = computed<number | null>(() =>
    typeof props.timings.audio_duration === 'number' ? props.timings.audio_duration : null
)

const total = computed<number | null>(() =>
    typeof props.timings.total === 'number' ? props.timings.total : null
)

const realtimeRatio = computed<string | null>(() => {
    if (audioDuration.value && total.value && total.value > 0) {
        return (audioDuration.value / total.value).toFixed(2) + '×'
    }
    return null
})

const rows = computed<Row[]>(() => {
    const denom = total.value && total.value > 0 ? total.value : 0
    const out: Row[] = []
    for (const key of STAGE_ORDER) {
        const v = props.timings[key]
        if (typeof v !== 'number') continue
        out.push({
            key,
            label: STAGE_LABELS[key] ?? key,
            seconds: v,
            pct: denom > 0 ? Math.min(100, (v / denom) * 100) : 0,
        })
    }
    return out
})

const hasData = computed<boolean>(() =>
    rows.value.length > 0 || audioDuration.value !== null || total.value !== null
)
</script>

<template>
    <section
        v-show="isVisible && hasData"
        id="section-timings"
        class="scroll-mt-20 bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border overflow-hidden"
    >
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-bg">
            <h3 class="text-base font-semibold text-gray-900 dark:text-white">
                处理耗时
            </h3>
        </div>

        <div class="p-6 text-gray-800 dark:text-gray-200 text-sm">
            <div
                v-if="audioDuration !== null"
                class="flex items-center justify-between pb-3 mb-3 border-b border-gray-100 dark:border-dark-border"
            >
                <span class="text-gray-600 dark:text-gray-400">视频时长</span>
                <span class="font-mono">{{ formatSeconds(audioDuration) }}</span>
            </div>

            <ul
                v-if="rows.length"
                class="space-y-2"
            >
                <li
                    v-for="row in rows"
                    :key="row.key"
                    class="grid grid-cols-[7rem_5rem_1fr] items-center gap-3"
                >
                    <span class="text-gray-600 dark:text-gray-400">{{ row.label }}</span>
                    <span class="font-mono text-right">{{ formatSeconds(row.seconds) }}</span>
                    <div class="h-1.5 bg-gray-100 dark:bg-dark-border rounded-full overflow-hidden">
                        <div
                            class="h-full bg-primary"
                            :style="{ width: `${row.pct}%` }"
                        />
                    </div>
                </li>
            </ul>

            <div
                v-if="total !== null"
                class="flex items-center justify-between pt-3 mt-3 border-t border-gray-100 dark:border-dark-border"
            >
                <span class="text-gray-700 dark:text-gray-300 font-medium">端到端</span>
                <span class="flex items-center gap-3">
                    <span class="font-mono">{{ formatSeconds(total) }}</span>
                    <span
                        v-if="realtimeRatio"
                        class="text-xs text-gray-500 dark:text-gray-400"
                    >实时比 {{ realtimeRatio }}</span>
                </span>
            </div>
        </div>
    </section>
</template>
