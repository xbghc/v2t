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
    <div class="flex min-h-screen items-center justify-center px-4">
        <div class="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
            <h1 class="mb-1 text-2xl font-bold">登录 Gist</h1>
            <p class="mb-6 text-sm text-gray-500">用邮箱验证码登录</p>

            <template v-if="step === 'email'">
                <input
                    v-model="email"
                    type="email"
                    placeholder="你的邮箱"
                    class="mb-3 w-full rounded-lg border border-gray-300 px-4 py-2.5 outline-none focus:border-black"
                    @keyup.enter="sendCode"
                >
                <button
                    :disabled="loading || !emailValid"
                    class="w-full rounded-lg bg-black py-2.5 font-medium text-white disabled:opacity-40"
                    @click="sendCode"
                >
                    {{ loading ? '发送中…' : '发送验证码' }}
                </button>
            </template>

            <template v-else>
                <p class="mb-3 text-sm text-gray-600">验证码已发至 {{ email }}</p>
                <input
                    v-model="code"
                    inputmode="numeric"
                    placeholder="6 位验证码"
                    class="mb-3 w-full rounded-lg border border-gray-300 px-4 py-2.5 tracking-widest outline-none focus:border-black"
                    @keyup.enter="doLogin"
                >
                <button
                    :disabled="loading"
                    class="mb-3 w-full rounded-lg bg-black py-2.5 font-medium text-white disabled:opacity-40"
                    @click="doLogin"
                >
                    {{ loading ? '登录中…' : '登录' }}
                </button>
                <button
                    :disabled="cooldown > 0"
                    class="w-full text-sm text-gray-500 disabled:opacity-40"
                    @click="sendCode"
                >
                    {{ cooldown > 0 ? `${cooldown}s 后可重发` : '重新发送' }}
                </button>
            </template>

            <p v-if="error" class="mt-4 text-sm text-red-500">{{ error }}</p>
        </div>
    </div>
</template>
