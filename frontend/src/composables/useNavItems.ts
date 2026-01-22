import { computed, type ComputedRef } from 'vue'
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/task'
import type { SideNavItem } from '@/types'

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
        audioUrl,
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
                icon: 'podcasts',
                hasContent: !!podcastScript.value || hasPodcastAudio.value,
                isLoading: podcastStreaming.value || podcastSynthesizing.value
            })
        }

        // 文章
        if (generateOptions.value.article || article.value) {
            items.push({
                key: 'article',
                label: '文章',
                icon: 'article',
                hasContent: !!article.value,
                isLoading: articleStreaming.value
            })
        }

        // 知乎（只有已有内容或正在生成时才显示）
        if (zhihuArticle.value || zhihuStreaming.value) {
            items.push({
                key: 'zhihu',
                label: '知乎',
                icon: 'edit_document',
                hasContent: !!zhihuArticle.value,
                isLoading: zhihuStreaming.value
            })
        }

        // 大纲
        if (generateOptions.value.outline || outline.value) {
            items.push({
                key: 'outline',
                label: '大纲',
                icon: 'format_list_bulleted',
                hasContent: !!outline.value,
                isLoading: outlineStreaming.value
            })
        }

        // 视频（始终显示）
        items.push({
            key: 'video',
            label: '视频',
            icon: 'videocam',
            hasContent: !!videoUrl.value,
            isLoading: workspaceStatus.value === 'downloading'
        })

        // 音频（始终显示）
        items.push({
            key: 'audio',
            label: '音频',
            icon: 'music_note',
            hasContent: !!audioUrl.value,
            isLoading: workspaceStatus.value === 'downloading'
        })

        // 字幕（始终显示）
        items.push({
            key: 'subtitle',
            label: '字幕',
            icon: 'subtitles',
            hasContent: !!transcript.value,
            isLoading: workspaceStatus.value === 'transcribing'
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
                icon: 'podcasts',
                hasContent: false,
                isLoading: false
            })
        }

        // 文章
        if (!generateOptions.value.article && !article.value) {
            items.push({
                key: 'article',
                label: '文章',
                icon: 'article',
                hasContent: false,
                isLoading: false
            })
        }

        // 知乎
        if (!zhihuArticle.value && !zhihuStreaming.value) {
            items.push({
                key: 'zhihu',
                label: '知乎',
                icon: 'edit_document',
                hasContent: false,
                isLoading: false
            })
        }

        // 大纲
        if (!generateOptions.value.outline && !outline.value) {
            items.push({
                key: 'outline',
                label: '大纲',
                icon: 'format_list_bulleted',
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
