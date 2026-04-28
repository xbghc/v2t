/**
 * 工作区状态机
 *
 * 状态流转（1:1 镜像后端 WorkspaceStatus）：
 *     idle → pending → processing → ready
 *                                ↘ failed
 *
 * processing 阶段细节通过：
 *   - context.progressText（来自后端 progress 字符串）
 *   - resource.ready 标志（哪些资源已产出）
 *   - APPEND_TRANSCRIPT 事件（流式逐段 transcript）
 */

import type { TranscriptSegmentMessage, WorkspaceErrorKind } from '@/types'

// --- 状态 ---
export type WorkspaceState =
    | 'idle'
    | 'pending'
    | 'processing'
    | 'ready'
    | 'failed'

// --- 事件 ---
export type WorkspaceEvent =
    | { type: 'SUBMIT'; workspaceId: string }
    | { type: 'STATUS_UPDATE'; status: 'pending' | 'processing' | 'ready' | 'failed'; error?: string; errorKind?: WorkspaceErrorKind }
    | { type: 'FAIL'; error: string; errorKind?: WorkspaceErrorKind }
    | { type: 'RESET' }
    | { type: 'LOAD_WORKSPACE'; status: 'pending' | 'processing' | 'ready' | 'failed' }
    | { type: 'UPDATE_RESOURCES'; title?: string; videoUrl?: string | null; transcript?: string; progressText?: string }
    | { type: 'APPEND_TRANSCRIPT'; segment: TranscriptSegmentMessage }

// --- Context ---
export interface WorkspaceContext {
    workspaceId: string | null
    title: string
    progressText: string
    progressTitle: string
    errorMessage: string
    errorKind: WorkspaceErrorKind
    videoUrl: string | null
    transcript: string
}

export function createInitialWorkspaceContext(): WorkspaceContext {
    return {
        workspaceId: null,
        title: '',
        progressText: '准备中...',
        progressTitle: '',
        errorMessage: '',
        errorKind: '',
        videoUrl: null,
        transcript: '',
    }
}

// --- 转换表 ---
type TransitionTarget = WorkspaceState | '*'
type TransitionMap = Record<WorkspaceState, Partial<Record<WorkspaceEvent['type'], TransitionTarget>>>

const TRANSITIONS: TransitionMap = {
    idle:       { SUBMIT: 'pending', LOAD_WORKSPACE: '*', RESET: 'idle' },
    pending:    { STATUS_UPDATE: '*', FAIL: 'failed', RESET: 'idle', UPDATE_RESOURCES: 'pending', APPEND_TRANSCRIPT: 'pending' },
    processing: { STATUS_UPDATE: '*', FAIL: 'failed', RESET: 'idle', UPDATE_RESOURCES: 'processing', APPEND_TRANSCRIPT: 'processing' },
    ready:      { RESET: 'idle', UPDATE_RESOURCES: 'ready', FAIL: 'failed', APPEND_TRANSCRIPT: 'ready' },
    failed:     { SUBMIT: 'pending', RESET: 'idle', LOAD_WORKSPACE: '*', UPDATE_RESOURCES: 'failed', APPEND_TRANSCRIPT: 'failed', STATUS_UPDATE: 'failed' },
}

const STATUS_TO_STATE: Record<string, WorkspaceState> = {
    pending: 'pending',
    processing: 'processing',
    ready: 'ready',
    failed: 'failed',
}

const PROGRESS_TEXT: Record<string, string> = {
    pending: '等待处理...',
    processing: '处理中...',
    ready: '准备生成内容...',
    failed: '处理失败',
}

function formatTimestamp(seconds: number): string {
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
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
        return {
            ...createInitialWorkspaceContext(),
            workspaceId: event.workspaceId,
            progressText: PROGRESS_TEXT.pending ?? '等待处理...',
        }
    case 'STATUS_UPDATE':
        return {
            ...ctx,
            // 后端 progress 字符串通过 UPDATE_RESOURCES 传递更具体的 progressText；
            // STATUS_UPDATE 只在出错时直接覆盖
            progressText: event.error ? '处理失败' : ctx.progressText,
            errorMessage: event.error ?? ctx.errorMessage,
            errorKind: event.errorKind ?? ctx.errorKind,
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
            // 只有后端落盘的 transcript 比累积版本更长（更完整）时才覆盖；
            // 否则保留流式累积内容，避免被 ready=False 的空 content 清掉
            transcript: event.transcript && event.transcript.length >= ctx.transcript.length
                ? event.transcript
                : ctx.transcript,
            progressText: event.progressText ?? ctx.progressText,
        }
    case 'APPEND_TRANSCRIPT': {
        const formatted = `[${formatTimestamp(event.segment.start)}] ${event.segment.text}`
        return {
            ...ctx,
            transcript: ctx.transcript ? `${ctx.transcript}\n${formatted}` : formatted,
        }
    }
    case 'FAIL':
        return {
            ...ctx,
            errorMessage: event.error,
            errorKind: event.errorKind ?? 'unknown',
            progressText: '处理失败',
        }
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
