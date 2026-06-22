import type { AuthResponse, UserResponse } from '@/types'
import { API_BASE, authHeaders } from './http'

/** 请求发送验证码到邮箱。 */
export async function requestCode(email: string): Promise<void> {
    const r = await fetch(`${API_BASE}/auth/request-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
    })
    if (!r.ok) {
        const d = (await r.json().catch(() => ({}))) as { detail?: string }
        throw new Error(d.detail || '验证码发送失败')
    }
}

/** 提交验证码登录，返回 token + 用户。 */
export async function verifyCode(email: string, code: string): Promise<AuthResponse> {
    const r = await fetch(`${API_BASE}/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code }),
    })
    const d = (await r.json()) as AuthResponse | { detail?: string }
    if (!r.ok) throw new Error((d as { detail?: string }).detail || '验证失败')
    return d as AuthResponse
}

/** 用当前 token 拉取登录用户（token 失效会 401）。 */
export async function fetchMe(): Promise<UserResponse> {
    const r = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() })
    if (!r.ok) throw new Error('获取用户信息失败')
    return r.json() as Promise<UserResponse>
}

/** 吊销当前 token。 */
export async function logout(): Promise<void> {
    await fetch(`${API_BASE}/auth/logout`, { method: 'POST', headers: authHeaders() })
}
