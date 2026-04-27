import type { Component } from 'vue'

// 后端通信 schema 从 @v2t/shared 统一导出（web 与 mobile 共享）
export * from '@v2t/shared'

/**
 * 内容标签标识符
 */
export type CurrentTab = 'article' | 'outline' | 'transcript' | 'podcast'

/**
 * 输入模式
 */
export type InputMode = 'url' | 'subtitle'

/**
 * 内容类型（状态机使用）
 */
export type ContentType = 'outline' | 'article' | 'podcast'

// ============ 生成选项 ============

/**
 * 生成选项
 */
export interface GenerateOptions {
    outline: boolean
    article: boolean
    podcast: boolean
}

// ============ 提示词类型 ============

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

// ============ 组件 Props 类型 ============

/**
 * AppHeader variant 类型
 */
export type HeaderVariant = 'default' | 'result'

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
export type SideNavKey = 'podcast' | 'article' | 'outline' | 'video' | 'subtitle'

/**
 * 可生成内容类型（SideNavKey 的子集）
 */
export type GeneratableContentKey = 'podcast' | 'article' | 'outline'

/**
 * 侧边导航项
 */
export interface SideNavItem {
    key: SideNavKey
    label: string
    icon: Component
    hasContent: boolean
    isLoading: boolean
}
