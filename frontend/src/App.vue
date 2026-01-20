<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/task'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import InitialPage from '@/components/InitialPage.vue'
import ResultPage from '@/components/ResultPage.vue'

const taskStore = useTaskStore()

// 解构响应式状态
const {
    page,
    url,
    taskId,
    taskStatus,
    currentTab,
    errorMessage,
    progress,
    result,
    currentContent,
    isStreaming
} = storeToRefs(taskStore)

// 解构方法
const { submitUrl, startNew, retryTask, copyContent } = taskStore
</script>

<template>
    <div class="relative flex min-h-screen w-full flex-col">
        <div class="layout-container flex h-full grow flex-col">
            <!-- Initial Page Layout -->
            <div
                v-if="page === 'initial'"
                class="flex flex-1 justify-center py-5 px-4 sm:px-8 md:px-20 lg:px-40"
            >
                <div class="layout-content-container flex w-full flex-col max-w-content flex-1">
                    <AppHeader />
                    <InitialPage
                        v-model:url="url"
                        @submit="submitUrl"
                    />
                    <AppFooter />
                </div>
            </div>

            <!-- Result Page Layout -->
            <template v-else-if="page === 'result'">
                <AppHeader
                    variant="result"
                    :show-new-button="true"
                    @new-task="startNew"
                />
                <ResultPage
                    v-model:current-tab="currentTab"
                    :task-id="taskId"
                    :task-status="taskStatus"
                    :error-message="errorMessage"
                    :progress="progress"
                    :result="result"
                    :current-content="currentContent"
                    :is-streaming="isStreaming"
                    @retry="retryTask"
                    @copy="copyContent"
                />
            </template>
        </div>
    </div>
</template>
