/**
 * 任务状态值，与后端 TaskStatus 枚举对应
 */
export type TaskStatus =
    | 'pending'
    | 'downloading'
    | 'transcribing'
    | 'generating'
    | 'completed'
    | 'failed'

/**
 * 内容标签标识符
 */
export type CurrentTab = 'article' | 'outline' | 'transcript'

/**
 * 页面状态
 */
export type PageState = 'initial' | 'result'

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
    download_only: boolean
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
export type MediaType = 'video' | 'audio'

/**
 * Tab 定义
 */
export interface TabDefinition {
    key: CurrentTab
    label: string
}
