/**
 * 后端通信 schema —— 适配层（web 与 mobile 共享）
 *
 * 绝大多数类型从 ./generated.ts 重导出，该文件由后端 OpenAPI 自动生成
 * （仓库根 `make generate`），请勿手改。本文件只做两件事：
 *   1. 把生成的 components['schemas'][...] 映射成前端惯用的扁平名
 *      （含若干历史命名，如 WorkspaceResourceResponse → WorkspaceResource）
 *   2. 补充 OpenAPI 覆盖不到的类型：SSE envelope、前端 camelCase 概念
 *
 * 改后端接口的正确姿势：改 Pydantic 模型 → `make generate` → 类型自动同步。
 * 枚举（status / content_type / error_kind 等）的唯一权威来源在后端 enums.py。
 */

import type { components } from './generated'

type Schemas = components['schemas']

// ===== 枚举（后端 Enum → 精确 union）=====
export type WorkspaceStatus = Schemas['WorkspaceStatus']
export type ResourceType = Schemas['ResourceType']
export type ResourceName = Schemas['ResourceName']
export type GenerationContentType = Schemas['GenerationContentType']
export type GenerationStatus = Schemas['GenerationStatus']
export type WorkspaceErrorKind = Schemas['WorkspaceErrorKind']

// ===== Workspace =====
export type WorkspaceResponse = Schemas['WorkspaceResponse']
export type WorkspaceResource = Schemas['WorkspaceResourceResponse']
export type GenerationTaskResponse = Schemas['GenerationTaskResponse']
export type CreateWorkspaceRequest = Schemas['CreateWorkspaceRequest']
export type WorkspaceLookupResponse = Schemas['WorkspaceLookupResponse']

// ===== 提示词 =====
export type PromptsResponse = Schemas['PromptsResponse']

// ===== B 站分 P 探测 =====
export type BilibiliPage = Schemas['BilibiliPageResponse']
export type BilibiliVideoMetaResponse = Schemas['BilibiliVideoMetaResponse']

// ===== 后台管理（运营统计）=====
// 注：daily / items / timings / error_kind 后端用 default_factory，响应里总是
// present（Pydantic 序列化输出空 []/{}），但 OpenAPI 的 required 未含它们，
// codegen 误标 optional。这些字段经 `**dict` 解包构造，去后端默认有缺键风险，
// 故在适配层按 wire 实际标 required（不谎报：序列化保证它们存在）。
export type PageviewRequest = Schemas['PageviewRequest']
export type AdminDailyPoint = Schemas['DailyPoint']

export type AdminHistoryItem = Omit<Schemas['HistoryItem'], 'timings'> & {
    timings: Record<string, number>
}
export type AdminHistoryResponse = Omit<Schemas['HistoryListResponse'], 'items'> & {
    items: AdminHistoryItem[]
}
export type AdminStatsResponse = Omit<
    Schemas['AdminStatsResponse'],
    'daily' | 'error_kind'
> & {
    daily: AdminDailyPoint[]
    error_kind: Record<string, number>
}

// ===== 认证（邮箱 OTP 登录）=====
export type UserResponse = Schemas['UserResponse']
export type AuthResponse = Schemas['AuthResponse']

// ===== OpenAPI 覆盖不到，手写保留 =====

/**
 * SSE 推送的单段转录增量。
 * 只在 GET /status-stream 里手动 yield，不是任何端点的 request/response model，
 * 故不进 OpenAPI。形状须与后端 TranscriptSegmentMessage(schemas.py) 保持一致。
 */
export interface TranscriptSegmentMessage {
    start: number
    end: number
    text: string
    chunk_index: number
}

/**
 * status-stream 的 SSE envelope（两类事件的联合）。
 */
export type StatusStreamEvent =
    | { type: 'workspace'; data: WorkspaceResponse }
    | { type: 'transcript.append'; data: TranscriptSegmentMessage }

/**
 * 前端内部使用的 camelCase 提示词对。
 * 注意：≠ 后端的 StreamRequest（snake_case 的 system_prompt / user_prompt）；
 * 在 api 层发请求前转换。保留手写以免与 StreamRequest 混淆。
 */
export interface StreamPrompts {
    systemPrompt: string
    userPrompt: string
}
