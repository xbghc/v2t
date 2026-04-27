import { computed, type ComputedRef } from 'vue'
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/task'
import type { SideNavItem } from '@/types'
import IconPodcasts from '~icons/material-symbols/podcasts'
import IconArticle from '~icons/material-symbols/article-outline'
import IconEditDocument from '~icons/material-symbols/edit-document-outline'
import IconFormatListBulleted from '~icons/material-symbols/format-list-bulleted'
import IconVideocam from '~icons/material-symbols/videocam-outline'
import IconSubtitles from '~icons/material-symbols/subtitles-outline'

export interface UseNavItemsReturn {
    navItems: ComputedRef<SideNavItem[]>
    disabledItems: ComputedRef<SideNavItem[]>
}

/**
 * 计算侧边导航项
 *
 * - navItems: 当前显示的导航项（已有内容或用户选择生成的）
 * - disabledItems: 可生成但未选择的项（仅在 ready 状态显示）
 */
export function useNavItems(): UseNavItemsReturn {
    const taskStore = useTaskStore()
    const {
        // 内容
        podcastScript,
        article,
        outline,
        zhihuArticle,
        // 资源
        videoUrl,
        transcript,
        hasPodcastAudio,
        // 流式状态
        podcastStreaming,
        podcastSynthesizing,
        articleStreaming,
        outlineStreaming,
        zhihuStreaming,
        // 生成选项
        generateOptions,
        // 工作区状态
        workspaceStatus
    } = storeToRefs(taskStore)

    const navItems = computed<SideNavItem[]>(() => {
        const items: SideNavItem[] = []

        // 播客
        if (generateOptions.value.podcast || podcastScript.value || hasPodcastAudio.value) {
            items.push({
                key: 'podcast',
                label: '播客',
                icon: IconPodcasts,
                hasContent: !!podcastScript.value || hasPodcastAudio.value,
                isLoading: podcastStreaming.value || podcastSynthesizing.value
            })
        }

        // 文章
        if (generateOptions.value.article || article.value) {
            items.push({
                key: 'article',
                label: '文章',
                icon: IconArticle,
                hasContent: !!article.value,
                isLoading: articleStreaming.value
            })
        }

        // 知乎（只有已有内容或正在生成时才显示）
        if (zhihuArticle.value || zhihuStreaming.value) {
            items.push({
                key: 'zhihu',
                label: '知乎',
                icon: IconEditDocument,
                hasContent: !!zhihuArticle.value,
                isLoading: zhihuStreaming.value
            })
        }

        // 大纲
        if (generateOptions.value.outline || outline.value) {
            items.push({
                key: 'outline',
                label: '大纲',
                icon: IconFormatListBulleted,
                hasContent: !!outline.value,
                isLoading: outlineStreaming.value
            })
        }

        const isProcessing = workspaceStatus.value === 'processing'

        // 字幕：仅在视频下载完后出现，与 ResultPage 区块同步
        if (videoUrl.value || transcript.value) {
            items.push({
                key: 'subtitle',
                label: '字幕',
                icon: IconSubtitles,
                hasContent: !!transcript.value,
                isLoading: isProcessing && !transcript.value
            })
        }

        // 视频：始终显示，processing 中且 URL 还没就绪 → loading
        items.push({
            key: 'video',
            label: '视频',
            icon: IconVideocam,
            hasContent: !!videoUrl.value,
            isLoading: isProcessing && !videoUrl.value
        })

        return items
    })

    const disabledItems = computed<SideNavItem[]>(() => {
        const items: SideNavItem[] = []

        // 只有当工作区状态为 ready 时，才显示可生成项
        if (workspaceStatus.value !== 'ready') {
            return items
        }

        // 播客（用户未选择且没有内容）
        if (!generateOptions.value.podcast && !podcastScript.value && !hasPodcastAudio.value) {
            items.push({
                key: 'podcast',
                label: '播客',
                icon: IconPodcasts,
                hasContent: false,
                isLoading: false
            })
        }

        // 文章
        if (!generateOptions.value.article && !article.value) {
            items.push({
                key: 'article',
                label: '文章',
                icon: IconArticle,
                hasContent: false,
                isLoading: false
            })
        }

        // 知乎
        if (!zhihuArticle.value && !zhihuStreaming.value) {
            items.push({
                key: 'zhihu',
                label: '知乎',
                icon: IconEditDocument,
                hasContent: false,
                isLoading: false
            })
        }

        // 大纲
        if (!generateOptions.value.outline && !outline.value) {
            items.push({
                key: 'outline',
                label: '大纲',
                icon: IconFormatListBulleted,
                hasContent: false,
                isLoading: false
            })
        }

        return items
    })

    return {
        navItems,
        disabledItems
    }
}
