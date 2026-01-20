<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()

// 判断是否为结果页
const isResultPage = computed(() => route.name === 'task')

// 新建任务并导航
const handleNewTask = () => {
    taskStore.startNew()
    router.push({ name: 'home' })
}
</script>

<template>
    <div class="relative flex min-h-screen w-full flex-col">
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
