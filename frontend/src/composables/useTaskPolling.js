import { ref, onUnmounted } from 'vue'
import { getTask } from '../api/task'

/**
 * 任务轮询 composable
 * @param {Function} onUpdate - 数据更新回调
 * @param {Function} onComplete - 任务完成回调
 * @param {Function} onFailed - 任务失败回调
 * @param {number} interval - 轮询间隔(ms)
 */
export function useTaskPolling({ onUpdate, onComplete, onFailed, interval = 2000 }) {
    const taskId = ref(null)
    let pollTimer = null

    const start = (id) => {
        taskId.value = id
        stop()
        pollTimer = setInterval(poll, interval)
        poll()
    }

    const stop = () => {
        if (pollTimer) {
            clearInterval(pollTimer)
            pollTimer = null
        }
    }

    const poll = async () => {
        if (!taskId.value) return

        try {
            const data = await getTask(taskId.value)
            onUpdate?.(data)

            if (data.status === 'completed') {
                stop()
                onComplete?.(data)
            } else if (data.status === 'failed') {
                stop()
                onFailed?.(data)
            }
        } catch (error) {
            console.error('轮询失败:', error)
        }
    }

    onUnmounted(stop)

    return {
        taskId,
        start,
        stop
    }
}
