<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/task'
import { useAuthStore } from '@/stores/auth'
import { fetchBilibiliPages, lookupWorkspaceBySeries } from '@/api/workspace'
import BilibiliPagesPicker from '@/components/BilibiliPagesPicker.vue'
import type { BilibiliPage, BilibiliVideoMetaResponse } from '@/types'
import IconLink from '~icons/material-symbols/link'
import IconChevronRight from '~icons/material-symbols/chevron-right'
import IconHelp from '~icons/material-symbols/help-outline'

const router = useRouter()
const taskStore = useTaskStore()
const auth = useAuthStore()
const { url, generateOptions, isDownloadOnly, prompts, promptsLoaded } = storeToRefs(taskStore)

const showAdvanced = ref(false)
const showInfo = ref(false)
const bilibiliMeta = ref<BilibiliVideoMetaResponse | null>(null)

const genOpts = [
    { key: 'outline', label: '大纲' },
    { key: 'article', label: '文章' },
    { key: 'podcast', label: '播客' },
] as const

const promptCards = [
    { title: '大纲', sys: 'outlineSystem', user: 'outlineUser', reset: () => taskStore.resetOutlinePrompts() },
    { title: '文章', sys: 'articleSystem', user: 'articleUser', reset: () => taskStore.resetArticlePrompts() },
    { title: '播客脚本', sys: 'podcastSystem', user: 'podcastUser', reset: () => taskStore.resetPodcastPrompts() },
] as const

// 「解调」可视化：左侧密集波形（原始视频信号）→ 右侧稀疏要点（提炼结果）
const waveform = [
    28, 42, 35, 58, 48, 70, 52, 86, 64, 54, 74, 40, 92, 60,
    46, 68, 50, 80, 44, 66, 36, 56, 48, 72, 42, 62, 34, 50,
]

// 波形从左到右由「噪声」逐渐解调成「信号」，无缝过渡到右侧三个要点点
function barClass(i: number): string {
    const r = i / (waveform.length - 1)
    if (r > 0.88) return 'bg-signal'
    if (r > 0.74) return 'bg-signal/55'
    return 'bg-ink/20'
}

function parseBilibiliPageIndex(rawUrl: string): number {
    try {
        const p = new URL(rawUrl).searchParams.get('p')
        const n = p ? parseInt(p, 10) : 1
        return Number.isFinite(n) && n > 0 ? n : 1
    } catch {
        return 1
    }
}

async function detectSeriesOptions(
    rawUrl: string,
): Promise<{ seriesBvid?: string; seriesIndex?: number } | undefined> {
    const bvMatch = rawUrl.match(/BV[0-9A-Za-z]{10}/)
    if (!bvMatch) return undefined
    const meta = bilibiliMeta.value?.bvid === bvMatch[0]
        ? bilibiliMeta.value
        : await fetchBilibiliPages(rawUrl)
    if (!meta || meta.pages.length < 2) return undefined
    return { seriesBvid: meta.bvid, seriesIndex: parseBilibiliPageIndex(rawUrl) }
}

const handleSubmitUrl = async () => {
    const seriesOpts = await detectSeriesOptions(url.value.trim())
    if (seriesOpts?.seriesBvid && seriesOpts.seriesIndex) {
        const existingId = await lookupWorkspaceBySeries(seriesOpts.seriesBvid, seriesOpts.seriesIndex)
        if (existingId) {
            router.push({ name: 'workspace', params: { id: existingId } })
            return
        }
    }
    const workspaceId = await taskStore.submitUrl(seriesOpts)
    if (workspaceId) {
        router.push({ name: 'workspace', params: { id: workspaceId } })
    } else if (taskStore.workspaceStatus === 'failed') {
        router.push({ name: 'workspace', params: { id: 'error' } })
    }
}

const handleSelectPage = async (page: BilibiliPage, bvid: string) => {
    const existingId = await lookupWorkspaceBySeries(bvid, page.page)
    if (existingId) {
        router.push({ name: 'workspace', params: { id: existingId } })
        return
    }
    const workspaceId = await taskStore.submitUrl({
        overrideUrl: page.url, seriesBvid: bvid, seriesIndex: page.page,
    })
    if (workspaceId) {
        router.push({ name: 'workspace', params: { id: workspaceId } })
    } else if (taskStore.workspaceStatus === 'failed') {
        router.push({ name: 'workspace', params: { id: 'error' } })
    }
}

const handleLogout = async () => {
    await auth.logout()
    router.push({ name: 'login' })
}

function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') showInfo.value = false
}

onMounted(() => {
    taskStore.loadPrompts()
    window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
    window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
    <main class="flex min-h-screen flex-col bg-canvas text-ink">
        <!-- 顶栏 -->
        <header class="flex items-center justify-between px-6 py-4 sm:px-8">
            <div class="flex items-center gap-2.5">
                <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-ink">
                    <svg width="17" height="17" viewBox="0 0 16 16" fill="none">
                        <rect x="2" y="6" width="2" height="4" rx="1" fill="#de8c2e" />
                        <rect x="6" y="2.5" width="2" height="11" rx="1" fill="#fff" />
                        <rect x="10" y="5" width="2" height="6" rx="1" fill="#fff" />
                    </svg>
                </span>
                <span class="font-title text-lg font-bold tracking-tight">Gist</span>
            </div>
            <div class="flex items-center gap-1">
                <!-- 「这是什么」问号图标 + popover -->
                <div class="relative z-40">
                    <button
                        class="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft transition-colors hover:bg-surface hover:text-ink"
                        :class="{ 'bg-surface text-ink': showInfo }"
                        aria-label="Gist 是什么"
                        :aria-expanded="showInfo"
                        @click="showInfo = !showInfo"
                    >
                        <IconHelp class="text-xl" />
                    </button>
                    <transition
                        enter-active-class="transition duration-150 ease-out"
                        enter-from-class="-translate-y-1 opacity-0"
                        enter-to-class="translate-y-0 opacity-100"
                        leave-active-class="transition duration-100 ease-in"
                        leave-from-class="opacity-100"
                        leave-to-class="opacity-0"
                    >
                        <div
                            v-if="showInfo"
                            class="absolute right-0 top-full mt-2 w-72 rounded-2xl border border-line bg-surface p-4 text-left shadow-[0_12px_40px_-12px_rgba(20,23,28,0.28)]"
                        >
                            <p class="text-[13px] leading-relaxed text-ink-soft">
                                贴上视频链接，Gist 把整段内容提炼成几条要点，帮你在点开之前判断它值不值得看。
                            </p>
                        </div>
                    </transition>
                </div>
                <button
                    class="text-sm text-ink-soft transition-colors hover:text-ink"
                    @click="handleLogout"
                >
                    退出登录
                </button>
            </div>
        </header>

        <!-- popover 背景遮罩：点击空白处关闭 -->
        <div v-if="showInfo" class="fixed inset-0 z-30" @click="showInfo = false"></div>

        <!-- Hero -->
        <section class="flex flex-1 flex-col items-center justify-center px-5 py-10">
            <div class="w-full max-w-xl">
                <!-- signature：解调可视化（噪声波形 → 提纯信号），纯视觉、无文字 -->
                <div class="flex items-center justify-center gap-5">
                    <div class="flex h-11 items-center gap-[3px]">
                        <span
                            v-for="(h, i) in waveform"
                            :key="i"
                            class="w-[3px] shrink-0 rounded-full transition-colors"
                            :class="barClass(i)"
                            :style="{ height: h + '%' }"
                        ></span>
                    </div>
                    <span class="text-xl text-ink-faint">→</span>
                    <div class="flex items-center gap-2">
                        <span class="h-2.5 w-2.5 rounded-full bg-signal"></span>
                        <span class="h-2.5 w-2.5 rounded-full bg-signal"></span>
                        <span class="h-2.5 w-2.5 rounded-full bg-signal"></span>
                    </div>
                </div>

                <!-- 输入框 -->
                <div class="mt-7">
                    <div class="flex items-stretch overflow-hidden rounded-2xl border border-line bg-surface shadow-[0_1px_2px_rgba(20,23,28,0.04),0_10px_30px_-14px_rgba(20,23,28,0.14)] transition focus-within:border-signal focus-within:shadow-[0_0_0_4px_var(--color-signal-soft)]">
                        <div class="flex items-center pl-4 text-ink-faint">
                            <IconLink class="text-xl" />
                        </div>
                        <input
                            v-model="url"
                            class="min-w-0 flex-1 bg-transparent px-3 py-4 text-[15px] text-ink placeholder:text-ink-faint focus:outline-none"
                            placeholder="粘贴 B站 / 抖音 / 小红书 / YouTube 链接"
                            @keypress.enter="handleSubmitUrl"
                        >
                        <button
                            class="m-1.5 shrink-0 rounded-xl bg-ink px-5 text-[15px] font-semibold text-surface transition-colors hover:bg-signal hover:text-signal-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
                            @click="handleSubmitUrl"
                        >
                            抓大意
                        </button>
                    </div>

                    <BilibiliPagesPicker
                        v-model:meta="bilibiliMeta"
                        :url="url"
                        class="mt-3"
                        @select="handleSelectPage"
                    />
                </div>

                <!-- 生成选项 chips -->
                <div class="mt-6 flex flex-col items-center gap-2.5">
                    <div class="flex flex-wrap items-center justify-center gap-2">
                        <span class="mr-1 text-sm text-ink-soft">生成</span>
                        <label
                            v-for="opt in genOpts"
                            :key="opt.key"
                            class="flex cursor-pointer select-none items-center rounded-full border px-4 py-1.5 text-sm font-medium transition-colors"
                            :class="generateOptions[opt.key]
                                ? 'border-signal bg-signal-soft text-signal-ink'
                                : 'border-line bg-surface text-ink-soft hover:border-ink-faint'"
                        >
                            <input v-model="generateOptions[opt.key]" type="checkbox" class="sr-only">
                            {{ opt.label }}
                        </label>
                    </div>
                    <p v-if="isDownloadOnly" class="font-mono text-xs text-ink-faint">
                        未选生成项 · 仅下载音视频
                    </p>
                </div>

                <!-- 高级 -->
                <div class="mt-5 text-center">
                    <button
                        type="button"
                        class="inline-flex items-center gap-1 text-sm text-ink-faint transition-colors hover:text-signal"
                        @click="showAdvanced = !showAdvanced"
                    >
                        <IconChevronRight class="text-base transition-transform duration-200" :class="{ 'rotate-90': showAdvanced }" />
                        自定义提示词
                    </button>
                </div>

                <!-- 高级面板 -->
                <div v-if="showAdvanced && promptsLoaded" class="mt-5 space-y-4">
                    <div
                        v-for="card in promptCards"
                        :key="card.sys"
                        class="rounded-2xl border border-line bg-surface p-5"
                    >
                        <div class="mb-3 flex items-center justify-between">
                            <h4 class="font-title text-sm font-semibold text-ink">{{ card.title }}提示词</h4>
                            <button
                                type="button"
                                class="text-xs text-ink-faint transition-colors hover:text-signal"
                                @click="card.reset()"
                            >
                                重置
                            </button>
                        </div>
                        <div class="space-y-3">
                            <div>
                                <label class="mb-1 block font-mono text-[11px] uppercase tracking-wider text-ink-faint">System</label>
                                <textarea
                                    v-model="prompts[card.sys]"
                                    rows="6"
                                    class="w-full resize-none rounded-xl border border-line bg-surface-sunk p-3 text-sm leading-relaxed text-ink focus:border-signal focus:outline-none focus:ring-2 focus:ring-signal-soft"
                                />
                            </div>
                            <div>
                                <label class="mb-1 block font-mono text-[11px] uppercase tracking-wider text-ink-faint">
                                    User <span class="text-ink-faint/70">· {content} = 转录内容</span>
                                </label>
                                <textarea
                                    v-model="prompts[card.user]"
                                    rows="3"
                                    class="w-full resize-none rounded-xl border border-line bg-surface-sunk p-3 text-sm leading-relaxed text-ink focus:border-signal focus:outline-none focus:ring-2 focus:ring-signal-soft"
                                />
                            </div>
                        </div>
                    </div>
                    <div class="text-center">
                        <button
                            type="button"
                            class="text-xs text-ink-faint transition-colors hover:text-signal"
                            @click="taskStore.resetPrompts()"
                        >
                            全部重置为默认值
                        </button>
                    </div>
                </div>
            </div>
        </section>

        <!-- 平台 footer -->
        <footer class="border-t border-line/70 px-5 py-7">
            <div class="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-ink-soft">
                <span class="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">支持</span>
                <span>哔哩哔哩</span>
                <span>抖音</span>
                <span>小红书</span>
                <span>YouTube</span>
            </div>
        </footer>
    </main>
</template>
