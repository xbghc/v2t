<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import GlobalToast from '@/components/GlobalToast.vue'

const auth = useAuthStore()

// 启动时用已存 token 拉用户；失效则 loadMe 内部清除（后续请求 401 会跳登录）
onMounted(() => { void auth.loadMe() })
</script>

<template>
    <GlobalToast />
    <!-- 每个页面自包含布局（首页 / 登录 / 结果页 / 后台各自管理） -->
    <router-view />
</template>
