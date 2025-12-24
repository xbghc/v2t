import { ref, onUnmounted } from 'vue'

/**
 * SSE 订阅 composable
 * @param {Object} options
 * @param {Function} options.onStatus - 状态更新回调
 * @param {Function} options.onDone - 完成回调
 * @param {Function} options.onError - 错误回调
 */
export function useSSE({ onStatus, onDone, onError }) {
    const eventSource = ref(null)

    /**
     * 开始订阅
     * @param {EventSource} source - EventSource 实例
     */
    const subscribe = (source) => {
        close()
        eventSource.value = source

        source.addEventListener('status', (event) => {
            try {
                const data = JSON.parse(event.data)
                onStatus?.(data)
            } catch (e) {
                console.error('解析 SSE 数据失败:', e)
            }
        })

        source.addEventListener('done', () => {
            onDone?.()
            close()
        })

        source.addEventListener('error', (event) => {
            // SSE 连接错误或服务端发送的 error 事件
            if (event.data) {
                try {
                    const data = JSON.parse(event.data)
                    onError?.(data.detail || '未知错误')
                } catch (e) {
                    onError?.('连接错误')
                }
            } else {
                // 连接错误，可能是网络问题或服务端关闭
                console.warn('SSE 连接错误')
            }
            close()
        })

        source.onerror = () => {
            // 浏览器原生错误处理
            if (source.readyState === EventSource.CLOSED) {
                close()
            }
        }
    }

    /**
     * 关闭连接
     */
    const close = () => {
        if (eventSource.value) {
            eventSource.value.close()
            eventSource.value = null
        }
    }

    onUnmounted(close)

    return {
        eventSource,
        subscribe,
        close
    }
}
