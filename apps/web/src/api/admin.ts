import type { AdminStatsResponse, AdminHistoryResponse } from '@/types'

// API 基础路径，与 workspace.ts 一致
const API_BASE = `${import.meta.env.BASE_URL}api`

/**
 * 获取后台仪表盘统计（累计 PV/UV、最近 N 天趋势、转录总数/成功率/失败分类）
 */
export async function getAdminStats(days = 14): Promise<AdminStatsResponse> {
    const response = await fetch(`${API_BASE}/admin/stats?days=${days}`)
    if (!response.ok) {
        throw new Error('获取统计数据失败')
    }
    return response.json() as Promise<AdminStatsResponse>
}

/**
 * 获取转录历史（分页，finished_at 倒序）
 */
export async function getAdminHistory(
    offset = 0,
    limit = 50,
): Promise<AdminHistoryResponse> {
    const params = new URLSearchParams({
        offset: String(offset),
        limit: String(limit),
    })
    const response = await fetch(`${API_BASE}/admin/history?${params}`)
    if (!response.ok) {
        throw new Error('获取转录历史失败')
    }
    return response.json() as Promise<AdminHistoryResponse>
}
