/**
 * 任务状态值，与后端 TaskStatus 枚举对应
 */
export type TaskStatus =
    | 'pending'
    | 'downloading'
    | 'transcribing'
    | 'ready_to_stream'
    | 'generating'
    | 'generating_podcast'
    | 'synthesizing'
    | 'completed'
    | 'failed'

/**
 * SSE 流式事件类型
 */
export type StreamEventType = 'outline' | 'article' | 'podcast_start' | 'podcast_done' | 'complete' | 'error'

/**
 * SSE 流式事件数据
 */
export interface StreamEventData {
    content?: string
    done?: boolean
    type?: string
    message?: string
    script?: string
    has_audio?: boolean
    error?: string
    status?: string
}

/**
 * 内容标签标识符
 */
export type CurrentTab = 'article' | 'outline' | 'transcript' | 'podcast'

/**
 * 页面状态
 */
export type PageState = 'initial' | 'result'

/**
 * 输入模式
 */
export type InputMode = 'url' | 'subtitle'

/**
 * 进度信息
 */
export interface ProgressInfo {
    title: string
    text: string
    percent: number
    step: string
}

/**
 * 任务结果数据
 */
export interface TaskResult {
    title: string
    has_video: boolean
    has_audio: boolean
    article: string
    outline: string
    transcript: string
    podcast_script: string
    has_podcast_audio: boolean
    podcast_error: string
}

/**
 * 状态映射条目
 */
export interface StatusMapEntry {
    text: string
    percent: number
    step: string
}

/**
 * 状态映射类型
 */
export type StatusMap = Partial<Record<TaskStatus, StatusMapEntry>>

// ============ API 类型 ============

/**
 * 创建任务请求参数
 */
export interface CreateTaskRequest {
    url: string
    generate_outline: boolean
    generate_article: boolean
    generate_podcast: boolean
    outline_system_prompt?: string
    outline_user_prompt?: string
    article_system_prompt?: string
    article_user_prompt?: string
    podcast_system_prompt?: string
    podcast_user_prompt?: string
}

/**
 * 生成选项
 */
export interface GenerateOptions {
    outline: boolean
    article: boolean
    podcast: boolean
}

/**
 * GET /api/prompts 响应 - 默认提示词
 */
export interface PromptsResponse {
    outline_system: string
    outline_user: string
    article_system: string
    article_user: string
    podcast_system: string
    podcast_user: string
}

/**
 * 自定义提示词参数
 */
export interface CustomPrompts {
    outlineSystem: string
    outlineUser: string
    articleSystem: string
    articleUser: string
    podcastSystem: string
    podcastUser: string
}

/**
 * POST /api/process 响应
 */
export interface CreateTaskResponse {
    task_id: string
    status: TaskStatus
    progress: string
}

/**
 * GET /api/task/{task_id} 响应
 */
export interface TaskResponse {
    task_id: string
    status: TaskStatus
    progress: string
    title: string
    has_video: boolean
    has_audio: boolean
    transcript: string
    outline: string
    article: string
    podcast_script: string
    has_podcast_audio: boolean
    podcast_error: string
    error: string
}

// ============ 组件 Props 类型 ============

/**
 * AppHeader variant 类型
 */
export type HeaderVariant = 'default' | 'result'

/**
 * MediaDownload 媒体类型
 */
export type MediaType = 'video' | 'audio' | 'podcast'

/**
 * Tab 定义
 */
export interface TabDefinition {
    key: CurrentTab
    label: string
}
