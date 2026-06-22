<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import GlobalToast from '@/components/GlobalToast.vue'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const auth = useAuthStore()

// 启动时用已存 token 拉用户；失效则 loadMe 内部清除（后续请求 401 会跳登录）
onMounted(() => { void auth.loadMe() })

// 判断是否为结果页
const isResultPage = computed(() => route.name === 'workspace')

// 判断是否为后台管理页（独立全屏布局，不套 Header/Footer/窄容器）
const isAdminPage = computed(() => route.name === 'admin')

// 新建任务并导航
const handleNewTask = () => {
    taskStore.startNew()
    router.push({ name: 'home' })
}
</script>

<template>
    <GlobalToast />
    <!-- Admin 页面自带完整布局 -->
    <router-view v-if="isAdminPage" />
    <div v-else class="relative flex min-h-screen w-full flex-col">
        <div class="layout-container flex h-full grow flex-col">
            <!-- Initial Page Layout -->
            <div
                v-if="!isResultPage"
                class="flex flex-1 justify-center py-5 px-4 sm:px-8 md:px-20 lg:px-40"
            >
                <div class="layout-content-container flex w-full flex-col max-w-content flex-1">
                    <AppHeader />
                    <router-view />
                    <AppFooter />
                </div>
            </div>

            <!-- Result Page Layout -->
            <template v-else>
                <AppHeader
                    variant="result"
                    :show-new-button="true"
                    @new-task="handleNewTask"
                />
                <router-view />
            </template>
        </div>
    </div>
</template>
