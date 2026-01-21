/**
 * 任务状态值，与后端 TaskStatus 枚举对应
 */
export type TaskStatus =
    | 'pending'
    | 'downloading'
    | 'transcribing'
    | 'ready'      // 转录完成，可以开始生成
    | 'completed'
    | 'failed'

/**
 * 内容标签标识符
 */
export type CurrentTab = 'article' | 'outline' | 'transcript' | 'podcast'

/**
 * 输入模式
 */
export type InputMode = 'url' | 'subtitle'

// ============ 任务类型 ============

/**
 * 视频任务结果（本地状态）
 */
export interface VideoTaskResult {
    title: string
    resource_id: string | null
    video_url: string | null
    audio_url: string | null
    transcript: string
}

// ============ API 类型 ============

/**
 * 创建任务请求参数
 */
export interface CreateTaskRequest {
    url: string
}

/**
 * 流式生成请求参数
 */
export interface StreamPrompts {
    systemPrompt: string
    userPrompt: string
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
 * 视频任务响应
 */
export interface VideoTaskResponse {
    task_id: string
    status: TaskStatus
    progress: string
    title: string
    resource_id: string | null
    video_url: string | null
    audio_url: string | null
    transcript: string
    error: string
}

/**
 * 大纲任务响应
 */
export interface OutlineTaskResponse {
    task_id: string
    status: TaskStatus
    progress: string
    outline: string
    error: string
}

/**
 * 文章任务响应
 */
export interface ArticleTaskResponse {
    task_id: string
    status: TaskStatus
    progress: string
    article: string
    error: string
}

/**
 * 播客任务响应
 */
export interface PodcastTaskResponse {
    task_id: string
    status: TaskStatus
    progress: string
    title: string
    podcast_script: string
    has_podcast_audio: boolean
    podcast_error: string
    error: string
}

/**
 * SSE 状态流事件数据（VideoTask）
 */
export interface VideoStatusStreamData {
    status: TaskStatus
    progress: string
    title: string
    resource_id: string | null
    video_url: string | null
    audio_url: string | null
    transcript: string
    error: string
}

/**
 * SSE 状态流事件数据（PodcastTask）
 */
export interface PodcastStatusStreamData {
    status: TaskStatus
    progress: string
    title: string
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

/**
 * 侧边导航项类型
 */
export type SideNavKey = 'podcast' | 'article' | 'outline' | 'video' | 'audio' | 'subtitle'

/**
 * 侧边导航项
 */
export interface SideNavItem {
    key: SideNavKey
    label: string
    icon: string
    hasContent: boolean
    isLoading: boolean
}
