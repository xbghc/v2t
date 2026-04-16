/**
 * 工作区状态机
 *
 * 状态流转（1:1 镜像后端 WorkspaceStatus）：
 * idle → pending → downloading → transcribing → ready
 *                                                 ↗
 *                               failed ←──────────
 */

// --- 状态 ---
export type WorkspaceState =
    | 'idle'
    | 'pending'
    | 'downloading'
    | 'transcribing'
    | 'ready'
    | 'failed'

// --- 事件 ---
export type WorkspaceEvent =
    | { type: 'SUBMIT'; workspaceId: string }
    | { type: 'STATUS_UPDATE'; status: 'pending' | 'downloading' | 'transcribing' | 'ready' | 'failed'; error?: string }
    | { type: 'FAIL'; error: string }
    | { type: 'RESET' }
    | { type: 'LOAD_WORKSPACE'; status: 'pending' | 'downloading' | 'transcribing' | 'ready' | 'failed' }
    | { type: 'UPDATE_RESOURCES'; title?: string; videoUrl?: string | null; audioUrl?: string | null; transcript?: string; progressText?: string }

// --- Context ---
export interface WorkspaceContext {
    workspaceId: string | null
    title: string
    progressText: string
    progressTitle: string
    errorMessage: string
    videoUrl: string | null
    audioUrl: string | null
    transcript: string
}

export function createInitialWorkspaceContext(): WorkspaceContext {
    return {
        workspaceId: null,
        title: '',
        progressText: '准备中...',
        progressTitle: '',
        errorMessage: '无法处理该视频链接，请检查链接是否正确且可公开访问，或尝试其他视频。',
        videoUrl: null,
        audioUrl: null,
        transcript: '',
    }
}

// --- 转换表 ---
// 值为 '*' 表示目标状态由事件 payload 决定
type TransitionTarget = WorkspaceState | '*'
type TransitionMap = Record<WorkspaceState, Partial<Record<WorkspaceEvent['type'], TransitionTarget>>>

const TRANSITIONS: TransitionMap = {
    idle:         { SUBMIT: 'pending', LOAD_WORKSPACE: '*', RESET: 'idle' },
    pending:      { STATUS_UPDATE: '*', FAIL: 'failed', RESET: 'idle', UPDATE_RESOURCES: 'pending' },
    downloading:  { STATUS_UPDATE: '*', FAIL: 'failed', RESET: 'idle', UPDATE_RESOURCES: 'downloading' },
    transcribing: { STATUS_UPDATE: '*', FAIL: 'failed', RESET: 'idle', UPDATE_RESOURCES: 'transcribing' },
    ready:        { RESET: 'idle', UPDATE_RESOURCES: 'ready', FAIL: 'failed' },
    failed:       { SUBMIT: 'pending', RESET: 'idle', LOAD_WORKSPACE: '*' },
}

const STATUS_TO_STATE: Record<string, WorkspaceState> = {
    pending: 'pending',
    downloading: 'downloading',
    transcribing: 'transcribing',
    ready: 'ready',
    failed: 'failed',
}

const PROGRESS_TEXT: Record<string, string> = {
    pending: '等待处理...',
    downloading: '正在下载视频...',
    transcribing: '正在转录音频...',
    ready: '准备生成内容...',
    failed: '处理失败',
}

function resolveNextState(current: WorkspaceState, target: TransitionTarget, event: WorkspaceEvent): WorkspaceState {
    if (target !== '*') return target

    if (event.type === 'STATUS_UPDATE' || event.type === 'LOAD_WORKSPACE') {
        return STATUS_TO_STATE[event.status] ?? current
    }
    return current
}

function updateContext(ctx: WorkspaceContext, event: WorkspaceEvent): WorkspaceContext {
    switch (event.type) {
    case 'SUBMIT':
        return { ...createInitialWorkspaceContext(), workspaceId: event.workspaceId }
    case 'STATUS_UPDATE':
        return {
            ...ctx,
            progressText: event.error ? '处理失败' : (PROGRESS_TEXT[event.status] ?? ctx.progressText),
            errorMessage: event.error ?? ctx.errorMessage,
        }
    case 'LOAD_WORKSPACE':
        return {
            ...ctx,
            progressText: PROGRESS_TEXT[event.status] ?? ctx.progressText,
        }
    case 'UPDATE_RESOURCES':
        return {
            ...ctx,
            title: event.title ?? ctx.title,
            progressTitle: event.title ?? ctx.progressTitle,
            videoUrl: event.videoUrl !== undefined ? event.videoUrl : ctx.videoUrl,
            audioUrl: event.audioUrl !== undefined ? event.audioUrl : ctx.audioUrl,
            transcript: event.transcript ?? ctx.transcript,
            progressText: event.progressText ?? ctx.progressText,
        }
    case 'FAIL':
        return { ...ctx, errorMessage: event.error, progressText: '处理失败' }
    case 'RESET':
        return createInitialWorkspaceContext()
    }
    return ctx
}

// --- 工厂函数 ---
export interface WorkspaceMachine {
    send: (event: WorkspaceEvent) => { state: WorkspaceState; context: WorkspaceContext }
    getState: () => WorkspaceState
    getContext: () => WorkspaceContext
}

export function createWorkspaceMachine(): WorkspaceMachine {
    let state: WorkspaceState = 'idle'
    let context: WorkspaceContext = createInitialWorkspaceContext()

    function send(event: WorkspaceEvent): { state: WorkspaceState; context: WorkspaceContext } {
        const target = TRANSITIONS[state]?.[event.type]
        if (target === undefined) {
            console.warn(`[WorkspaceMachine] Invalid transition: ${state} + ${event.type}`)
            return { state, context }
        }

        state = resolveNextState(state, target, event)
        context = updateContext(context, event)
        return { state, context }
    }

    return {
        send,
        getState: () => state,
        getContext: () => context,
    }
}
