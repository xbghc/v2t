import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserResponse } from '@/types'
import {
    requestCode as apiRequestCode,
    verifyCode,
    fetchMe,
    logout as apiLogout,
} from '@/api/auth'
import { getToken, setToken } from '@/api/http'

export const useAuthStore = defineStore('auth', () => {
    const token = ref<string | null>(getToken())
    const user = ref<UserResponse | null>(null)
    const isLoggedIn = computed(() => !!token.value)

    async function requestCode(email: string): Promise<void> {
        await apiRequestCode(email)
    }

    async function verify(email: string, code: string): Promise<void> {
        const res = await verifyCode(email, code)
        token.value = res.token
        setToken(res.token)
        user.value = res.user
    }

    /** 启动时用已存的 token 拉用户；失效则清掉。 */
    async function loadMe(): Promise<void> {
        if (!token.value) return
        try {
            user.value = await fetchMe()
        } catch {
            token.value = null
            setToken(null)
        }
    }

    async function logout(): Promise<void> {
        try {
            await apiLogout()
        } catch {
            /* 忽略：本地清理为准 */
        }
        token.value = null
        setToken(null)
        user.value = null
    }

    return { token, user, isLoggedIn, requestCode, verify, loadMe, logout }
})
