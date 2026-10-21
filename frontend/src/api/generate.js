import request, { BASE } from './request'
import { useAuth } from '../store/auth'

/** 提交生成任务（payload 含 request_id 幂等键） */
export function submitGenerate(payload) {
  return request.post('/api/generate', payload)
}

/** 分页查询历史记录 */
export function fetchHistory(limit = 12, offset = 0) {
  return request.get('/api/history', { params: { limit, offset } })
}

/** 查询单个任务状态（WebSocket 断线时兜底） */
export function fetchTask(taskId) {
  return request.get(`/api/task/${taskId}`)
}

/** 图片显示地址：<img> 标签无法带 header，通过 token 查询参数鉴权 */
export function imageUrl(taskId) {
  const { token } = useAuth()
  return `${BASE}/api/image/${taskId}?token=${encodeURIComponent(token.value)}`
}

/** 图片下载地址（Content-Disposition: attachment） */
export function imageDownloadUrl(taskId) {
  return `${imageUrl(taskId)}&download=1`
}

/** 由后端 http 地址推导出 WebSocket 地址（同样通过 token 查询参数鉴权） */
export function wsUrl(taskId) {
  const { token } = useAuth()
  return `${BASE.replace(/^http/, 'ws')}/ws/${taskId}?token=${encodeURIComponent(token.value)}`
}
