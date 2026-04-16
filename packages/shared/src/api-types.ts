/**
 * 后端通信 schema（与 backend WorkspaceStatus / API 响应 1:1 对应）
 * web 与 mobile 共享此定义
 */

// 工作区状态（与后端 WorkspaceStatus 枚举对应）
export type WorkspaceStatus =
    | 'pending'
    | 'downloading'
    | 'transcribing'
    | 'ready'
    | 'failed'

// 资源类型
export type ResourceType = 'video' | 'audio' | 'text'

// 工作区资源
export interface WorkspaceResource {
    resource_id: string
    name: string  // video, audio, transcript, outline, article, podcast, zhihu
    resource_type: ResourceType
    download_url: string | null
    content: string | null
    created_at: number
}

// GET /api/workspaces/{id} 响应
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

// POST /api/workspaces 请求
export interface CreateWorkspaceRequest {
    url: string
}

// GET /api/prompts 响应
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

// POST /api/workspaces/{id}/stream/{type} 请求参数
export interface StreamPrompts {
    systemPrompt: string
    userPrompt: string
}
