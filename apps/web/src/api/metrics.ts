// API 基础路径，与 workspace.ts 一致
const API_BASE = `${import.meta.env.BASE_URL}api`

const VISITOR_KEY = 'v2t_visitor_id'

/**
 * 获取（或首次生成）当前浏览器的匿名访客 ID，用于后端 UV 去重。
 * localStorage 不可用（隐私模式等）时返回空串，后端只计 PV。
 */
function getVisitorId(): string {
    try {
        let id = localStorage.getItem(VISITOR_KEY)
        if (!id) {
            id = crypto.randomUUID()
            localStorage.setItem(VISITOR_KEY, id)
        }
        return id
    } catch {
        return ''
    }
}

/**
 * 上报一次页面访问（PV/UV 埋点）。
 *
 * fire-and-forget：埋点绝不能影响用户体验，任何失败都静默吞掉。
 */
export function reportPageview(path: string): void {
    try {
        const body = JSON.stringify({ path, visitor_id: getVisitorId() })
        void fetch(`${API_BASE}/metrics/pageview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body,
            keepalive: true,
        }).catch(() => {})
    } catch {
        // 构造请求阶段失败也不抛
    }
}
