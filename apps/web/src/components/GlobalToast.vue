<script setup lang="ts">
import { useToastStore } from '@/stores/toast'
import type { ToastType } from '@/stores/toast'
import type { Component } from 'vue'
import IconError from '~icons/material-symbols/error-outline'
import IconCheckCircle from '~icons/material-symbols/check-circle-outline'
import IconWarning from '~icons/material-symbols/warning-outline'
import IconInfo from '~icons/material-symbols/info-outline'
import IconClose from '~icons/material-symbols/close'

const toastStore = useToastStore()

const getTypeStyles = (type: ToastType): string => {
    switch (type) {
    case 'error':
        return 'bg-red-500 text-white'
    case 'success':
        return 'bg-green-500 text-white'
    case 'warning':
        return 'bg-yellow-500 text-white'
    case 'info':
        return 'bg-blue-500 text-white'
    }
}

const getIcon = (type: ToastType): Component => {
    switch (type) {
    case 'error':
        return IconError
    case 'success':
        return IconCheckCircle
    case 'warning':
        return IconWarning
    case 'info':
        return IconInfo
    }
}
</script>

<template>
    <Teleport to="body">
        <div class="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 pointer-events-none">
            <TransitionGroup name="toast">
                <div
                    v-for="toast in toastStore.toasts"
                    :key="toast.id"
                    class="pointer-events-auto flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg min-w-[200px] max-w-[400px]"
                    :class="getTypeStyles(toast.type)"
                >
                    <component
                        :is="getIcon(toast.type)"
                        class="text-xl flex-shrink-0"
                    />
                    <span class="text-sm flex-1">{{ toast.message }}</span>
                    <button
                        class="flex-shrink-0 opacity-70 hover:opacity-100 transition-opacity"
                        @click="toastStore.removeToast(toast.id)"
                    >
                        <IconClose class="text-lg" />
                    </button>
                </div>
            </TransitionGroup>
        </div>
    </Teleport>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
    transition: all 0.3s ease;
}

.toast-enter-from {
    opacity: 0;
    transform: translateY(-20px);
}

.toast-leave-to {
    opacity: 0;
    transform: translateY(-20px);
}

.toast-move {
    transition: transform 0.3s ease;
}
</style>
