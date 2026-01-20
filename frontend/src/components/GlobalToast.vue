<script setup lang="ts">
import { useToastStore } from '@/stores/toast'
import type { ToastType } from '@/stores/toast'

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

const getIcon = (type: ToastType): string => {
    switch (type) {
    case 'error':
        return 'error'
    case 'success':
        return 'check_circle'
    case 'warning':
        return 'warning'
    case 'info':
        return 'info'
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
                    <span class="material-symbols-outlined text-xl flex-shrink-0">
                        {{ getIcon(toast.type) }}
                    </span>
                    <span class="text-sm flex-1">{{ toast.message }}</span>
                    <button
                        class="flex-shrink-0 opacity-70 hover:opacity-100 transition-opacity"
                        @click="toastStore.removeToast(toast.id)"
                    >
                        <span class="material-symbols-outlined text-lg">close</span>
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
