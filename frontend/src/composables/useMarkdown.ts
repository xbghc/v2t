import { computed, toValue, type MaybeRefOrGetter, type ComputedRef } from 'vue'
import { marked, type MarkedOptions } from 'marked'

export interface UseMarkdownOptions {
    /**
     * marked 解析配置
     */
    markedOptions?: MarkedOptions
    /**
     * 解析失败时的回退值
     * @default ''
     */
    fallback?: string
}

/**
 * 将 Markdown 内容渲染为 HTML
 *
 * @param content Markdown 内容（支持 ref、getter 或普通值）
 * @param options 配置选项
 * @returns 渲染后的 HTML 字符串
 *
 * @example
 * ```ts
 * const markdown = ref('# Hello')
 * const html = useMarkdown(markdown)
 * // html.value === '<h1>Hello</h1>'
 * ```
 */
export function useMarkdown(
    content: MaybeRefOrGetter<string>,
    options: UseMarkdownOptions = {}
): ComputedRef<string> {
    const { markedOptions, fallback = '' } = options

    return computed(() => {
        const value = toValue(content)
        if (!value) return ''

        try {
            return marked.parse(value, markedOptions) as string
        } catch {
            return fallback
        }
    })
}
