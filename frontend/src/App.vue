<template>
  <div class="page">
    <header>
      <h1>AI 图文生成</h1>
      <p class="subtitle">Vue3 + FastAPI + Celery + Redis + 火山方舟 Seedream</p>
    </header>

    <GeneratorForm :loading="loading" @submit="onSubmit" />

    <!-- 实时状态提示：排队中 / 生成中 / 成功 / 失败 -->
    <div v-if="currentStatus" class="status card">
      <span class="dot" :class="currentStatus"></span>
      <span>当前任务：{{ statusText(currentStatus) }}</span>
      <span v-if="currentError" class="error">（{{ currentError }}）</span>
    </div>

    <Gallery :items="history" @preview="previewItem = $event" />

    <!-- 图片预览弹窗 -->
    <div v-if="previewItem" class="modal" @click.self="previewItem = null">
      <img :src="previewItem.image_url" :alt="previewItem.prompt" title="右键可保存图片" />
      <p>{{ previewItem.prompt }}</p>
      <button class="ghost" @click="previewItem = null">关闭</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import GeneratorForm from './components/GeneratorForm.vue'
import Gallery from './components/Gallery.vue'
import { submitGenerate, fetchHistory, fetchTask, wsUrl } from './api'

const loading = ref(false) // 生成中，禁用按钮
const currentStatus = ref('') // 当前任务状态
const currentError = ref('') // 当前任务错误信息
const history = ref([]) // 历史记录列表
const previewItem = ref(null) // 预览的图片项

let ws = null

const STATUS_TEXT = { queued: '排队中', generating: '生成中', success: '成功', failed: '失败' }
function statusText(s) {
  return STATUS_TEXT[s] || s
}

/** 加载历史记录 */
async function loadHistory() {
  try {
    const { data } = await fetchHistory(50, 0)
    if (data.code === 0) history.value = data.data
  } catch (e) {
    console.error('加载历史失败', e)
  }
}

/** 提交生成任务 */
async function onSubmit(payload) {
  loading.value = true
  currentStatus.value = ''
  currentError.value = ''
  try {
    const { data } = await submitGenerate(payload)
    const taskId = data.task_id
    currentStatus.value = 'queued'
    connectWS(taskId)
    // 建立 WebSocket 后先查一次状态，避免任务过快完成而错过推送
    const { data: t } = await fetchTask(taskId)
    applyStatus(t.data)
  } catch (e) {
    currentError.value = e.response?.data?.detail || e.message
    loading.value = false
  }
}

/** 建立 WebSocket，监听任务进度 */
function connectWS(taskId) {
  closeWS()
  ws = new WebSocket(wsUrl(taskId))
  ws.onmessage = (ev) => {
    try {
      applyStatus(JSON.parse(ev.data))
    } catch (e) {
      console.error('WebSocket 消息解析失败', e)
    }
  }
  ws.onerror = () => console.error('WebSocket 连接出错')
}

/** 应用任务状态到界面 */
function applyStatus(msg) {
  currentStatus.value = msg.status
  if (msg.error) currentError.value = msg.error
  // 任务结束（成功或失败）时结束 loading 并刷新画廊
  if (msg.status === 'success' || msg.status === 'failed') {
    loading.value = false
    closeWS()
    loadHistory()
  }
}

function closeWS() {
  if (ws) {
    ws.close()
    ws = null
  }
}

onMounted(loadHistory)
onBeforeUnmount(closeWS)
</script>
