<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const step = ref<'email' | 'code'>('email')
const email = ref('')
const code = ref('')
const error = ref('')
const loading = ref(false)
const cooldown = ref(0)
let timer: number | undefined

const emailValid = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim()))

function startCooldown(): void {
    cooldown.value = 60
    timer = window.setInterval(() => {
        cooldown.value--
        if (cooldown.value <= 0 && timer) {
            clearInterval(timer)
            timer = undefined
        }
    }, 1000)
}
onUnmounted(() => {
    if (timer) clearInterval(timer)
})

async function sendCode(): Promise<void> {
    error.value = ''
    if (!emailValid.value) {
        error.value = '请输入有效的邮箱'
        return
    }
    loading.value = true
    try {
        await auth.requestCode(email.value.trim())
        step.value = 'code'
        startCooldown()
    } catch (e) {
        error.value = (e as Error).message
    } finally {
        loading.value = false
    }
}

async function doLogin(): Promise<void> {
    error.value = ''
    if (!code.value.trim()) {
        error.value = '请输入验证码'
        return
    }
    loading.value = true
    try {
        await auth.verify(email.value.trim(), code.value.trim())
        const redirect = (route.query.redirect as string) || '/'
        router.replace(redirect)
    } catch (e) {
        error.value = (e as Error).message
    } finally {
        loading.value = false
    }
}
</script>

<template>
    <main class="flex min-h-screen items-center justify-center bg-canvas px-5 text-ink">
        <div class="w-full max-w-sm">
            <!-- 品牌 -->
            <div class="mb-8 flex flex-col items-center gap-3">
                <span class="flex h-12 w-12 items-center justify-center rounded-2xl bg-ink">
                    <svg width="22" height="22" viewBox="0 0 16 16" fill="none">
                        <rect x="2" y="6" width="2" height="4" rx="1" fill="#de8c2e" />
                        <rect x="6" y="2.5" width="2" height="11" rx="1" fill="#fff" />
                        <rect x="10" y="5" width="2" height="6" rx="1" fill="#fff" />
                    </svg>
                </span>
                <div class="text-center">
                    <h1 class="font-title text-2xl font-bold tracking-tight">登录 Gist</h1>
                    <p class="mt-1 text-sm text-ink-soft">看视频前，先抓个大意</p>
                </div>
            </div>

            <!-- 卡片 -->
            <div class="rounded-2xl border border-line bg-surface p-6 shadow-[0_1px_2px_rgba(20,23,28,0.04),0_12px_32px_-16px_rgba(20,23,28,0.16)]">
                <template v-if="step === 'email'">
                    <label class="mb-1.5 block font-mono text-[11px] uppercase tracking-wider text-ink-faint">邮箱</label>
                    <input
                        v-model="email"
                        type="email"
                        placeholder="you@example.com"
                        class="w-full rounded-xl border border-line bg-surface px-4 py-3 text-[15px] text-ink placeholder:text-ink-faint transition focus:border-signal focus:outline-none focus:ring-2 focus:ring-signal-soft"
                        @keyup.enter="sendCode"
                    >
                    <button
                        :disabled="loading || !emailValid"
                        class="mt-3 w-full rounded-xl bg-ink py-3 text-[15px] font-semibold text-surface transition-colors hover:bg-signal hover:text-signal-ink disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-ink disabled:hover:text-surface"
                        @click="sendCode"
                    >
                        {{ loading ? '发送中…' : '发送验证码' }}
                    </button>
                </template>

                <template v-else>
                    <p class="mb-4 text-sm text-ink-soft">
                        验证码已发送至 <span class="font-medium text-ink">{{ email }}</span>
                    </p>
                    <label class="mb-1.5 block font-mono text-[11px] uppercase tracking-wider text-ink-faint">验证码</label>
                    <input
                        v-model="code"
                        inputmode="numeric"
                        placeholder="6 位数字"
                        class="w-full rounded-xl border border-line bg-surface px-4 py-3 font-mono text-lg tracking-[0.3em] text-ink placeholder:font-sans placeholder:text-base placeholder:tracking-normal placeholder:text-ink-faint transition focus:border-signal focus:outline-none focus:ring-2 focus:ring-signal-soft"
                        @keyup.enter="doLogin"
                    >
                    <button
                        :disabled="loading"
                        class="mt-3 w-full rounded-xl bg-ink py-3 text-[15px] font-semibold text-surface transition-colors hover:bg-signal hover:text-signal-ink disabled:cursor-not-allowed disabled:opacity-40"
                        @click="doLogin"
                    >
                        {{ loading ? '登录中…' : '登录' }}
                    </button>
                    <button
                        :disabled="cooldown > 0"
                        class="mt-3 w-full text-center text-sm text-ink-faint transition-colors enabled:hover:text-signal disabled:cursor-not-allowed"
                        @click="sendCode"
                    >
                        {{ cooldown > 0 ? `${cooldown}s 后可重新发送` : '重新发送验证码' }}
                    </button>
                </template>

                <p v-if="error" class="mt-3 text-sm text-red-500">{{ error }}</p>
            </div>

            <p class="mt-6 text-center font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">
                AI 视频预审
            </p>
        </div>
    </main>
</template>
