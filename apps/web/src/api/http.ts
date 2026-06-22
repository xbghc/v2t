/**
 * 统一的 API base + token 管理 + 401 处理。
 * auth 与各业务 api 共用，token 存 localStorage。
 */

export const API_BASE = `${import.meta.env.BASE_URL}api/v1`

const TOKEN_KEY = 'v2t_token'

export function getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
}

/** 业务请求统一带上的鉴权头（未登录时为空对象）。 */
export function authHeaders(): Record<string, string> {
    const t = getToken()
    return t ? { Authorization: `Bearer ${t}` } : {}
}

/**
 * 收到 401：清 token 并跳登录页（带 redirect 回当前页）。
 * 用 window.location 而非 router，避免 api 层耦合路由实例。
 */
export function onUnauthorized(): void {
    setToken(null)
    const here = window.location.pathname + window.location.search
    if (!here.startsWith('/login')) {
        window.location.href = `/login?redirect=${encodeURIComponent(here)}`
    }
}
