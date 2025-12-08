<script setup>
import InitialPage from './components/InitialPage.vue'
import ResultPage from './components/ResultPage.vue'
import { useTask } from './composables/useTask'

const {
    page,
    url,
    downloadOnly,
    taskId,
    taskStatus,
    currentTab,
    errorMessage,
    progress,
    result,
    isProcessing,
    isFailed,
    hasTextContent,
    currentContent,
    isContentLoading,
    contentLoadingText,
    startNew,
    retryTask,
    submitUrl,
    copyContent
} = useTask()
</script>

<template>
    <InitialPage
        v-if="page === 'initial'"
        :url="url"
        :download-only="downloadOnly"
        @update:url="url = $event"
        @update:download-only="downloadOnly = $event"
        @submit="submitUrl"
    />
    <ResultPage
        v-else-if="page === 'result'"
        :task-id="taskId"
        :task-status="taskStatus"
        :current-tab="currentTab"
        :error-message="errorMessage"
        :progress="progress"
        :result="result"
        :is-processing="isProcessing"
        :is-failed="isFailed"
        :has-text-content="hasTextContent"
        :current-content="currentContent"
        :is-content-loading="isContentLoading"
        :content-loading-text="contentLoadingText"
        @start-new="startNew"
        @retry-task="retryTask"
        @copy-content="copyContent"
        @update:current-tab="currentTab = $event"
    />
</template>
