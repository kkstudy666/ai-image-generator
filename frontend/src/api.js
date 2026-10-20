import axios from 'axios'

// 后端地址：可通过 .env 文件中的 VITE_API_BASE 覆盖，默认本地 8000 端口
const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const api = axios.create({ baseURL: BASE, timeout: 30000 })

/** 提交生成任务 */
export function submitGenerate(payload) {
  return api.post('/api/generate', payload)
}

/** 查询历史记录 */
export function fetchHistory(limit = 50, offset = 0) {
  return api.get('/api/history', { params: { limit, offset } })
}

/** 查询单个任务状态（WebSocket 断线时兜底） */
export function fetchTask(taskId) {
  return api.get(`/api/task/${taskId}`)
}

/** 由后端 http 地址推导出 WebSocket 地址 */
export function wsUrl(taskId) {
  return BASE.replace(/^http/, 'ws') + `/ws/${taskId}`
}
