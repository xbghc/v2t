import { computed, type ComputedRef } from 'vue'
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/task'

export interface ContentVisibility {
    showPodcast: ComputedRef<boolean>
    showArticle: ComputedRef<boolean>
    showOutline: ComputedRef<boolean>
    showZhihu: ComputedRef<boolean>
}

/**
 * 计算各内容区块的显示条件
 *
 * 显示规则：
 * - 已有内容或正在流式生成
 * - 用户选择了生成且工作区已准备好
 */
export function useContentVisibility(): ContentVisibility {
    const taskStore = useTaskStore()
    const {
        // 内容
        podcastScript,
        article,
        outline,
        zhihuArticle,
        // 音频
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

    const showPodcast = computed(() => {
        // 已有内容或正在生成
        if (podcastScript.value || hasPodcastAudio.value || podcastStreaming.value || podcastSynthesizing.value) {
            return true
        }
        // 用户选择了生成，且工作区已准备好
        if (generateOptions.value.podcast && workspaceStatus.value === 'ready') {
            return true
        }
        return false
    })

    const showArticle = computed(() => {
        // 已有内容或正在生成
        if (article.value || articleStreaming.value) return true
        // 用户选择了生成，且工作区已准备好
        if (generateOptions.value.article && workspaceStatus.value === 'ready') return true
        return false
    })

    const showOutline = computed(() => {
        // 已有内容或正在生成
        if (outline.value || outlineStreaming.value) return true
        // 用户选择了生成，且工作区已准备好
        if (generateOptions.value.outline && workspaceStatus.value === 'ready') return true
        return false
    })

    const showZhihu = computed(() => {
        // 知乎只有在已有内容或正在生成时才显示
        return !!zhihuArticle.value || zhihuStreaming.value
    })

    return {
        showPodcast,
        showArticle,
        showOutline,
        showZhihu
    }
}
