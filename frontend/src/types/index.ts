/**
 * 工作区状态值，与后端 WorkspaceStatus 枚举对应
 */
export type WorkspaceStatus =
    | 'pending'
    | 'downloading'
    | 'transcribing'
    | 'ready'      // 转录完成，可以开始生成
    | 'failed'

/**
 * 资源类型
 */
export type ResourceType = 'video' | 'audio' | 'text'

/**
 * 内容标签标识符
 */
export type CurrentTab = 'article' | 'outline' | 'transcript' | 'podcast' | 'zhihu'

/**
 * 输入模式
 */
export type InputMode = 'url' | 'subtitle'

// ============ Workspace 类型 ============

/**
 * 工作区资源
 */
export interface WorkspaceResource {
    resource_id: string
    name: string  // video, audio, transcript, outline, article, podcast, zhihu
    resource_type: ResourceType
    download_url: string | null
    content: string | null  // text 类型直接返回内容
    created_at: number
}

/**
 * 工作区响应
 */
export interface WorkspaceResponse {
    workspace_id: string
    url: string
    title: string
    status: WorkspaceStatus
    progress: string
    error: string
    resources: WorkspaceResource[]
    created_at: number
    last_accessed_at: number
}

/**
 * 创建工作区请求
 */
export interface CreateWorkspaceRequest {
    url: string
}

// ============ 生成选项 ============

/**
 * 生成选项
 */
export interface GenerateOptions {
    outline: boolean
    article: boolean
    podcast: boolean
}

/**
 * 流式生成请求参数
 */
export interface StreamPrompts {
    systemPrompt: string
    userPrompt: string
}

// ============ 提示词类型 ============

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
    zhihu_system: string
    zhihu_user: string
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
    zhihuSystem: string
    zhihuUser: string
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
export type SideNavKey = 'podcast' | 'article' | 'outline' | 'zhihu' | 'video' | 'audio' | 'subtitle'

/**
 * 可生成内容类型（SideNavKey 的子集）
 */
export type GeneratableContentKey = 'podcast' | 'article' | 'outline' | 'zhihu'

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
