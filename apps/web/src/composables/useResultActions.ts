import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useToastStore } from '@/stores/toast'
import type { SideNavKey, GeneratableContentKey, WorkspaceStatus } from '@/types'

const CONTENT_LABELS: Record<GeneratableContentKey, string> = {
    podcast: '播客',
    article: '文章',
    outline: '大纲',
    zhihu: '知乎文章'
}

export interface LoadingTextState {
    workspaceStatus: WorkspaceStatus
    podcastSynthesizing: boolean
    podcastStreaming: boolean
    articleStreaming: boolean
    outlineStreaming: boolean
    zhihuStreaming: boolean
}

/**
 * 获取区块的加载状态文本
 */
export function getLoadingText(key: SideNavKey, state: LoadingTextState): string {
    if (state.workspaceStatus === 'downloading') return '正在下载视频...'
    if (state.workspaceStatus === 'transcribing') return '正在转录音频...'
    if (key === 'podcast' && state.podcastSynthesizing) return '正在合成播客音频...'
    if (key === 'podcast' && state.podcastStreaming) return '正在生成播客脚本...'
    if (key === 'article' && state.articleStreaming) return '正在生成文章...'
    if (key === 'outline' && state.outlineStreaming) return '正在生成大纲...'
    if (key === 'zhihu' && state.zhihuStreaming) return '正在生成知乎文章...'
    return '加载中...'
}

/**
 * 判断 key 是否为可生成内容类型
 */
function isGeneratableKey(key: SideNavKey): key is GeneratableContentKey {
    return key === 'podcast' || key === 'article' || key === 'outline' || key === 'zhihu'
}

/**
 * ResultPage 操作函数集合
 */
export function useResultActions() {
    const router = useRouter()
    const taskStore = useTaskStore()
    const toastStore = useToastStore()

    /**
     * 重试失败的任务
     */
    const handleRetry = async () => {
        const workspaceId = await taskStore.retryTask()
        if (workspaceId) {
            router.push({ name: 'workspace', params: { id: workspaceId } })
        }
    }

    /**
     * 生成单个内容类型
     */
    const handleGenerateContent = (key: SideNavKey) => {
        if (isGeneratableKey(key)) {
            taskStore.generateSingleContent(key)
            toastStore.showToast(`正在生成${CONTENT_LABELS[key]}...`, 'info')
        }
    }

    /**
     * 复制内容到剪贴板
     */
    const copyContent = (content: string) => {
        if (!content) return
        navigator.clipboard.writeText(content).then(() => {
            toastStore.showToast('已复制到剪贴板', 'success')
        }).catch(() => {
            toastStore.showToast('复制失败，请手动选择复制', 'error')
        })
    }

    /**
     * 滚动到指定区块
     */
    const scrollToSection = (key: SideNavKey) => {
        const element = document.getElementById(`section-${key}`)
        element?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }

    return {
        handleRetry,
        handleGenerateContent,
        copyContent,
        scrollToSection
    }
}
