import { ref, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import type {
    ContentGeneratorState,
    ContentGeneratorEvent,
    ContentType
} from '@/types'

/**
 * 内容生成器状态机
 * 管理单个内容类型的生成状态流转
 */
export interface ContentGenerator {
    // 状态
    state: Ref<ContentGeneratorState>
    content: Ref<string>
    streamingContent: Ref<string>
    error: Ref<string>
    audioUrl: Ref<string | null>

    // 计算属性
    isIdle: ComputedRef<boolean>
    isStreaming: ComputedRef<boolean>
    isSynthesizing: ComputedRef<boolean>
    isCompleted: ComputedRef<boolean>
    isFailed: ComputedRef<boolean>
    isLoading: ComputedRef<boolean>
    displayContent: ComputedRef<string>
    hasContent: ComputedRef<boolean>

    // 状态转换方法
    send: (event: ContentGeneratorEvent) => void
    reset: () => void

    // 清理函数
    cleanup: Ref<(() => void) | null>
}

/**
 * 状态转换表
 * 定义每个状态可以接受的事件及转换后的状态
 */
const transitions: Record<ContentGeneratorState, Partial<Record<ContentGeneratorEvent['type'], ContentGeneratorState>>> = {
    idle: {
        START: 'streaming',
        RESET: 'idle'
    },
    streaming: {
        CHUNK: 'streaming',
        SYNTHESIZE_START: 'synthesizing',
        COMPLETE: 'completed',
        ERROR: 'failed',
        RESET: 'idle'
    },
    synthesizing: {
        COMPLETE: 'completed',
        ERROR: 'failed',
        RESET: 'idle'
    },
    completed: {
        START: 'streaming',
        RESET: 'idle'
    },
    failed: {
        START: 'streaming',
        RESET: 'idle'
    }
}

/**
 * 创建内容生成器状态机
 */
export function createContentGenerator(type: ContentType): ContentGenerator {
    const state: Ref<ContentGeneratorState> = ref('idle')
    const content: Ref<string> = ref('')
    const streamingContent: Ref<string> = ref('')
    const error: Ref<string> = ref('')
    const audioUrl: Ref<string | null> = ref(null)
    const cleanup: Ref<(() => void) | null> = ref(null)

    // 计算属性
    const isIdle = computed(() => state.value === 'idle')
    const isStreaming = computed(() => state.value === 'streaming')
    const isSynthesizing = computed(() => state.value === 'synthesizing')
    const isCompleted = computed(() => state.value === 'completed')
    const isFailed = computed(() => state.value === 'failed')
    const isLoading = computed(() => state.value === 'streaming' || state.value === 'synthesizing')
    const displayContent = computed(() => isLoading.value ? streamingContent.value : content.value)
    const hasContent = computed(() => content.value.length > 0 || streamingContent.value.length > 0)

    /**
     * 发送事件触发状态转换
     */
    function send(event: ContentGeneratorEvent): void {
        const currentState = state.value
        const allowedTransitions = transitions[currentState]
        const nextState = allowedTransitions[event.type]

        if (!nextState) {
            console.warn(`[${type}] Invalid transition: ${currentState} + ${event.type}`)
            return
        }

        // 执行状态转换副作用
        switch (event.type) {
        case 'START':
            streamingContent.value = ''
            error.value = ''
            break
        case 'CHUNK':
            streamingContent.value += event.content
            break
        case 'COMPLETE':
            content.value = streamingContent.value
            if (event.audioUrl) {
                audioUrl.value = event.audioUrl
            }
            if (event.audioError) {
                error.value = event.audioError
            }
            break
        case 'ERROR':
            error.value = event.error
            break
        case 'RESET':
            content.value = ''
            streamingContent.value = ''
            error.value = ''
            audioUrl.value = null
            if (cleanup.value) {
                cleanup.value()
                cleanup.value = null
            }
            break
        }

        state.value = nextState
    }

    /**
     * 重置状态机
     */
    function reset(): void {
        send({ type: 'RESET' })
    }

    return {
        state,
        content,
        streamingContent,
        error,
        audioUrl,
        isIdle,
        isStreaming,
        isSynthesizing,
        isCompleted,
        isFailed,
        isLoading,
        displayContent,
        hasContent,
        send,
        reset,
        cleanup
    }
}

/**
 * 内容生成器集合
 */
export interface ContentGenerators {
    outline: ContentGenerator
    article: ContentGenerator
    podcast: ContentGenerator
    zhihu: ContentGenerator
}

/**
 * 创建所有内容生成器
 */
export function createContentGenerators(): ContentGenerators {
    return {
        outline: createContentGenerator('outline'),
        article: createContentGenerator('article'),
        podcast: createContentGenerator('podcast'),
        zhihu: createContentGenerator('zhihu')
    }
}
