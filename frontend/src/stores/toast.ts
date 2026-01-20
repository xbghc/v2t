import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ToastType = 'error' | 'success' | 'warning' | 'info'

export interface Toast {
    id: number
    message: string
    type: ToastType
    duration: number
}

let toastId = 0

export const useToastStore = defineStore('toast', () => {
    const toasts = ref<Toast[]>([])

    const showToast = (
        message: string,
        type: ToastType = 'info',
        duration: number = 3000
    ): number => {
        const id = ++toastId
        toasts.value.push({ id, message, type, duration })

        if (duration > 0) {
            setTimeout(() => {
                removeToast(id)
            }, duration)
        }

        return id
    }

    const removeToast = (id: number): void => {
        const index = toasts.value.findIndex(t => t.id === id)
        if (index !== -1) {
            toasts.value.splice(index, 1)
        }
    }

    return {
        toasts,
        showToast,
        removeToast
    }
})

export type ToastStore = ReturnType<typeof useToastStore>
