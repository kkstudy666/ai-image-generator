// WebSocket 封装：自动重连（指数退避）+ 断线后轮询兜底补发状态
import { fetchTask, wsUrl } from './api/generate'

const MAX_RETRY = 5          // 最大重连次数
const POLL_INTERVAL = 2000   // 兜底轮询间隔（毫秒）

/**
 * 订阅任务进度。
 * @param {string} taskId 任务 ID
 * @param {(msg: object) => void} onMessage 收到状态消息（含 status / error 等字段）
 * @returns {{ close: () => void }} 停止订阅
 */
export function subscribeTask(taskId, onMessage) {
  let ws = null
  let retry = 0
  let pollTimer = null
  let stopped = false

  function cleanupWs() {
    if (ws) {
      ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null
      try { ws.close() } catch (e) { /* 忽略关闭异常 */ }
      ws = null
    }
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  }

  // WebSocket 无法建立或重连耗尽后，降级为轮询 REST 接口兜底补发状态
  function startPolling() {
    if (pollTimer || stopped) return
    pollTimer = setInterval(async () => {
      if (stopped) { stopPolling(); return }
      try {
        const { data } = await fetchTask(taskId)
        const t = data.data
        onMessage(t)
        if (t.status === 'success' || t.status === 'failed') stop()
      } catch (e) { /* 忽略单次轮询失败，下次继续 */ }
    }, POLL_INTERVAL)
  }

  function connect() {
    if (stopped) return
    cleanupWs()
    stopPolling()

    ws = new WebSocket(wsUrl(taskId))

    ws.onopen = () => { retry = 0 }

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        onMessage(msg)
        if (msg.status === 'success' || msg.status === 'failed') stop()
      } catch (e) { /* 忽略解析失败的消息 */ }
    }

    ws.onclose = () => {
      if (stopped) return
      // 断线重连：指数退避 1s -> 2s -> 4s -> 8s -> 16s
      if (retry < MAX_RETRY) {
        retry += 1
        setTimeout(connect, 2 ** retry * 500)
      } else {
        startPolling() // 重连耗尽，降级为轮询
      }
    }

    ws.onerror = () => { /* onclose 会随后触发，统一在 onclose 中处理 */ }
  }

  function stop() {
    stopped = true
    cleanupWs()
    stopPolling()
  }

  connect()

  return { close: stop }
}
