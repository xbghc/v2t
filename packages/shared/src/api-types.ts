/**
 * 后端通信 schema（与 backend WorkspaceStatus / API 响应 1:1 对应）
 * web 与 mobile 共享此定义
 */

// 工作区状态（与后端 WorkspaceStatus 枚举对应）
// 流式管道下 downloading / transcribing 已合并为 processing
export type WorkspaceStatus =
    | 'pending'
    | 'processing'
    | 'ready'
    | 'failed'

// 资源类型
export type ResourceType = 'video' | 'audio' | 'text'

// 工作区资源
export interface WorkspaceResource {
    resource_id: string
    name: string  // video, audio, transcript, outline, article, podcast
    resource_type: ResourceType
    download_url: string | null
    content: string | null
    ready: boolean  // 资源是否已完成产出
    created_at: number
}

// SSE 推送的单段转录（envelope: type=transcript.append）
export interface TranscriptSegmentMessage {
    start: number
    end: number
    text: string
    chunk_index: number
}

// SSE envelope 联合类型
export type StatusStreamEvent =
    | { type: 'workspace'; data: WorkspaceResponse }
    | { type: 'transcript.append'; data: TranscriptSegmentMessage }

// 失败原因分类（决定 UI 行为：是否给重试按钮等）
//   video_too_long    — 视频时长超限（重试无意义，应改链接）
//   download_failed   — 下载失败（建议重试）
//   transcribe_failed — 转录失败（建议重试）
//   unknown           — 未分类
export type WorkspaceErrorKind =
    | ''
    | 'video_too_long'
    | 'download_failed'
    | 'transcribe_failed'
    | 'unknown'

// GET /api/workspaces/{id} 响应
export interface WorkspaceResponse {
    workspace_id: string
    url: string
    title: string
    status: WorkspaceStatus
    progress: string
    error: string  // 用户可读的友好消息（直接展示）
    error_kind: WorkspaceErrorKind  // 机器可读分类
    resources: WorkspaceResource[]
    created_at: number
    last_accessed_at: number
    // B 站分 P 系列元数据（非分 P 视频时为空字符串 + 0）
    series_bvid: string
    series_index: number
}

// POST /api/workspaces 请求
export interface CreateWorkspaceRequest {
    url: string
    series_bvid?: string
    series_index?: number
}

// GET /api/workspaces/lookup 响应
export interface WorkspaceLookupResponse {
    workspace_id: string | null
}

// === B 站分 P 探测 ===

// 单个分 P
export interface BilibiliPage {
    page: number      // 1-based 序号
    cid: number
    title: string
    duration: number  // 秒
    url: string
}

// GET /api/bilibili/pages 响应
export interface BilibiliVideoMetaResponse {
    bvid: string
    title: string
    owner: string
    cover_url: string
    pages: BilibiliPage[]
}

// GET /api/prompts 响应
export interface PromptsResponse {
    outline_system: string
    outline_user: string
    article_system: string
    article_user: string
    podcast_system: string
    podcast_user: string
}

// POST /api/workspaces/{id}/stream/{type} 请求参数
export interface StreamPrompts {
    systemPrompt: string
    userPrompt: string
}
