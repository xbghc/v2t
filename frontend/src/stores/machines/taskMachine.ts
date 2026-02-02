import { ref, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import type {
    TaskMachineState,
    TaskMachineEvent,
    WorkspaceStatus
} from '@/types'

/**
 * 任务状态机接口
 */
export interface TaskMachine {
    // 状态
    state: Ref<TaskMachineState>
    workspaceId: Ref<string | null>
    workspaceStatus: Ref<WorkspaceStatus>
    errorMessage: Ref<string>
    progressText: Ref<string>
    progressTitle: Ref<string>

    // 计算属性
    isIdle: ComputedRef<boolean>
    isSubmitting: ComputedRef<boolean>
    isProcessing: ComputedRef<boolean>
    isGenerating: ComputedRef<boolean>
    isCompleted: ComputedRef<boolean>
    isFailed: ComputedRef<boolean>
    isWorking: ComputedRef<boolean>

    // 状态转换方法
    send: (event: TaskMachineEvent) => void
    reset: () => void
}

/**
 * 状态转换表
 */
const transitions: Record<TaskMachineState, Partial<Record<TaskMachineEvent['type'], TaskMachineState>>> = {
    idle: {
        SUBMIT: 'submitting',
        STATUS_UPDATE: 'processing',  // 从 URL 加载已有工作区
        RESET: 'idle'
    },
    submitting: {
        SUBMIT_SUCCESS: 'processing',
        SUBMIT_ERROR: 'failed',
        RESET: 'idle'
    },
    processing: {
        STATUS_UPDATE: 'processing',
        READY_TO_GENERATE: 'generating',
        SUBMIT_ERROR: 'failed',
        RESET: 'idle'
    },
    generating: {
        GENERATION_COMPLETE: 'completed',
        SUBMIT_ERROR: 'failed',
        RESET: 'idle'
    },
    completed: {
        SUBMIT: 'submitting',
        RESET: 'idle'
    },
    failed: {
        SUBMIT: 'submitting',
        RETRY: 'submitting',
        RESET: 'idle'
    }
}

/**
 * 根据后端状态获取进度文本
 */
function getProgressTextFromStatus(status: WorkspaceStatus): string {
    switch (status) {
    case 'pending': return '等待处理...'
    case 'downloading': return '正在下载视频...'
    case 'transcribing': return '正在转录音频...'
    case 'ready': return '准备生成内容...'
    case 'failed': return '处理失败'
    default: return '处理中...'
    }
}

/**
 * 创建任务状态机
 */
export function createTaskMachine(): TaskMachine {
    const state: Ref<TaskMachineState> = ref('idle')
    const workspaceId: Ref<string | null> = ref(null)
    const workspaceStatus: Ref<WorkspaceStatus> = ref('pending')
    const errorMessage: Ref<string> = ref('无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。')
    const progressText: Ref<string> = ref('准备中...')
    const progressTitle: Ref<string> = ref('')

    // 计算属性
    const isIdle = computed(() => state.value === 'idle')
    const isSubmitting = computed(() => state.value === 'submitting')
    const isProcessing = computed(() => state.value === 'processing')
    const isGenerating = computed(() => state.value === 'generating')
    const isCompleted = computed(() => state.value === 'completed')
    const isFailed = computed(() => state.value === 'failed')
    const isWorking = computed(() =>
        state.value === 'submitting' ||
        state.value === 'processing' ||
        state.value === 'generating'
    )

    /**
     * 发送事件触发状态转换
     */
    function send(event: TaskMachineEvent): void {
        const currentState = state.value
        const allowedTransitions = transitions[currentState]
        const nextState = allowedTransitions[event.type]

        if (!nextState) {
            console.warn(`[TaskMachine] Invalid transition: ${currentState} + ${event.type}`)
            return
        }

        // 执行状态转换副作用
        switch (event.type) {
        case 'SUBMIT':
            progressText.value = '准备中...'
            progressTitle.value = ''
            break
        case 'SUBMIT_SUCCESS':
            workspaceId.value = event.workspaceId
            break
        case 'SUBMIT_ERROR':
            errorMessage.value = event.error
            break
        case 'STATUS_UPDATE':
            workspaceStatus.value = event.status
            progressText.value = event.data.progress || getProgressTextFromStatus(event.status)
            progressTitle.value = event.data.title
            if (event.data.error) {
                errorMessage.value = event.data.error
            }
            // 如果后端状态是 ready，转换到 generating
            if (event.status === 'ready') {
                state.value = 'generating'
                progressText.value = '正在生成内容...'
                return
            }
            // 如果后端状态是 failed，转换到 failed
            if (event.status === 'failed') {
                state.value = 'failed'
                return
            }
            break
        case 'READY_TO_GENERATE':
            progressText.value = '正在生成内容...'
            break
        case 'GENERATION_COMPLETE':
            progressText.value = '处理完成'
            break
        case 'RESET':
            workspaceId.value = null
            workspaceStatus.value = 'pending'
            errorMessage.value = '无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。'
            progressText.value = '准备中...'
            progressTitle.value = ''
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
        workspaceId,
        workspaceStatus,
        errorMessage,
        progressText,
        progressTitle,
        isIdle,
        isSubmitting,
        isProcessing,
        isGenerating,
        isCompleted,
        isFailed,
        isWorking,
        send,
        reset
    }
}
