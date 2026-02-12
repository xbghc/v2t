/**
 * 内容状态机（参数化，4 种内容类型复用）
 *
 * 状态流转：
 * idle → streaming → done
 *          ↓           ↗
 *       synthesizing  (仅 podcast)
 *          ↓
 *        failed
 */

import type { ContentType } from '@/types'

// --- 状态 ---
export type ContentState =
    | 'idle'
    | 'streaming'
    | 'synthesizing'  // 仅 podcast：脚本完成，TTS 合成中
    | 'done'
    | 'failed'

// --- 事件 ---
export type ContentEvent =
    | { type: 'START' }
    | { type: 'CHUNK'; content: string }
    | { type: 'SYNTHESIZE_START' }
    | { type: 'COMPLETE'; audioUrl?: string; audioError?: string }
    | { type: 'FAIL'; error?: string }
    | { type: 'RESET' }

// --- Context ---
export interface ContentContext {
    streamBuffer: string
    finalContent: string
    audioUrl: string | null   // 仅 podcast
    audioError: string        // 仅 podcast
    error: string
}

export function createInitialContentContext(): ContentContext {
    return {
        streamBuffer: '',
        finalContent: '',
        audioUrl: null,
        audioError: '',
        error: '',
    }
}

// --- 转换表 ---
type TransitionMap = Record<ContentState, Partial<Record<ContentEvent['type'], ContentState>>>

const TRANSITIONS: TransitionMap = {
    idle:         { START: 'streaming', RESET: 'idle' },
    streaming:    { CHUNK: 'streaming', COMPLETE: 'done', SYNTHESIZE_START: 'synthesizing', FAIL: 'failed', RESET: 'idle' },
    synthesizing: { COMPLETE: 'done', FAIL: 'failed', RESET: 'idle' },
    done:         { START: 'streaming', RESET: 'idle' },
    failed:       { START: 'streaming', RESET: 'idle' },
}

function updateContext(ctx: ContentContext, event: ContentEvent): ContentContext {
    switch (event.type) {
    case 'START':
        return { ...createInitialContentContext() }
    case 'CHUNK':
        return { ...ctx, streamBuffer: ctx.streamBuffer + event.content }
    case 'SYNTHESIZE_START':
        return ctx
    case 'COMPLETE':
        return {
            ...ctx,
            finalContent: ctx.streamBuffer,
            audioUrl: event.audioUrl ?? ctx.audioUrl,
            audioError: event.audioError ?? ctx.audioError,
        }
    case 'FAIL':
        return { ...ctx, error: event.error ?? '生成失败' }
    case 'RESET':
        return createInitialContentContext()
    }
}

// --- 工厂函数 ---
export interface ContentMachine {
    send: (event: ContentEvent) => { state: ContentState; context: ContentContext }
    getState: () => ContentState
    getContext: () => ContentContext
    contentType: ContentType
}

export function createContentMachine(contentType: ContentType): ContentMachine {
    let state: ContentState = 'idle'
    let context: ContentContext = createInitialContentContext()

    function send(event: ContentEvent): { state: ContentState; context: ContentContext } {
        // 非 podcast 不允许进入 synthesizing
        if (event.type === 'SYNTHESIZE_START' && contentType !== 'podcast') {
            return { state, context }
        }

        const target = TRANSITIONS[state]?.[event.type]
        if (target === undefined) {
            console.warn(`[ContentMachine:${contentType}] Invalid transition: ${state} + ${event.type}`)
            return { state, context }
        }

        state = target
        context = updateContext(context, event)
        return { state, context }
    }

    return {
        send,
        getState: () => state,
        getContext: () => context,
        contentType,
    }
}
