<template>
  <div class="page">
    <!-- 未登录：显示登录/注册页 -->
    <LoginView v-if="!isLoggedIn" @authed="onAuthed" />

    <template v-else>
      <header>
        <h1>AI 图文生成</h1>
        <p class="subtitle">Vue3 + FastAPI + Celery + Redis + 火山方舟 Seedream</p>
        <div class="user-bar">
          <span>你好，{{ user?.username }}</span>
          <button class="ghost" @click="logout">退出登录</button>
        </div>
      </header>

      <GeneratorForm :loading="loading" @submit="onSubmit" />

      <!-- 实时进度条 + 状态文字 + 失败重试 -->
      <ProgressBar :status="currentStatus" :error="currentError" @retry="retryLast" />

      <Gallery
        :items="history"
        :loading="loadingMore"
        :has-more="hasMore"
        @preview="previewItem = $event"
        @load-more="loadHistory()"
      />
    </template>

    <!-- 图片预览弹窗：大图 + 生成参数回看 + 一键下载 -->
    <div v-if="previewItem" class="modal" @click.self="previewItem = null">
      <img :src="imageUrl(previewItem.task_id)" :alt="previewItem.prompt" />
      <div class="modal-info">
        <p class="modal-prompt">{{ previewItem.prompt }}</p>
        <dl class="modal-params">
          <div><dt>负面提示词</dt><dd>{{ previewItem.negative_prompt || '无' }}</dd></div>
          <div><dt>尺寸</dt><dd>{{ previewItem.size }}</dd></div>
          <div><dt>类型</dt><dd>{{ previewItem.task_type === 'img2img' ? '图生图' : '文生图' }}</dd></div>
          <div><dt>创建时间</dt><dd>{{ previewItem.created_at }}</dd></div>
        </dl>
        <div class="modal-actions">
          <button class="primary" @click="downloadImage(previewItem)">下载图片</button>
          <button class="ghost" @click="previewItem = null">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import LoginView from './components/LoginView.vue'
import GeneratorForm from './components/GeneratorForm.vue'
import Gallery from './components/Gallery.vue'
import ProgressBar from './components/ProgressBar.vue'
import { submitGenerate, fetchHistory, imageDownloadUrl, imageUrl } from './api/generate'
import { useAuth } from './store/auth'
import { subscribeTask } from './ws'

const { user, isLoggedIn, logout } = useAuth()

const loading = ref(false)      // 是否正在生成
const currentStatus = ref('')   // 当前任务状态
const currentError = ref('')    // 当前任务错误信息
const history = ref([])         // 历史记录列表
const pageSize = 12             // 每页条数
const offset = ref(0)
const hasMore = ref(true)
const loadingMore = ref(false)
const previewItem = ref(null)   // 预览的图片项
const lastPayload = ref(null)   // 最近一次提交参数（供重试使用）

let subscription = null // 当前 WebSocket 订阅句柄

/** 加载历史记录（reset=true 从头加载） */
async function loadHistory(reset = false) {
  if (loadingMore.value) return
  loadingMore.value = true
  try {
    if (reset) { offset.value = 0; hasMore.value = true; history.value = [] }
    const { data } = await fetchHistory(pageSize, offset.value)
    if (data.code === 0) {
      const list = data.data
      history.value = reset ? list : history.value.concat(list)
      offset.value += list.length
      hasMore.value = list.length === pageSize
    }
  } catch (e) {
    console.error('加载历史失败', e)
  } finally {
    loadingMore.value = false
  }
}

/** 登录成功后拉取当前用户作品 */
function onAuthed() {
  loadHistory(true)
}

/** 提交生成任务 */
async function onSubmit(payload) {
  loading.value = true
  currentStatus.value = 'queued'
  currentError.value = ''
  lastPayload.value = payload
  try {
    const { data } = await submitGenerate(payload)
    applyStatus({ status: data.status })
    // 订阅 WebSocket（自动重连 + 轮询兜底补发状态）
    subscription?.close()
    subscription = subscribeTask(data.task_id, applyStatus)
  } catch (e) {
    currentError.value = e.response?.data?.detail || e.message
    currentStatus.value = 'failed'
    loading.value = false
  }
}

/** 失败重试：用新的幂等键重新提交上一次参数 */
function retryLast() {
  if (lastPayload.value) {
    onSubmit({ ...lastPayload.value, request_id: crypto.randomUUID() })
  }
}

/** 应用任务状态到界面 */
function applyStatus(msg) {
  currentStatus.value = msg.status
  if (msg.error) currentError.value = msg.error
  // 任务结束（成功或失败）时结束 loading 并刷新画廊
  if (msg.status === 'success' || msg.status === 'failed') {
    loading.value = false
    subscription?.close()
    subscription = null
    loadHistory(true)
  }
}

/** 一键下载：打开带 token 的下载地址（后端返回 Content-Disposition: attachment） */
function downloadImage(item) {
  window.open(imageDownloadUrl(item.task_id), '_blank')
}

onBeforeUnmount(() => subscription?.close())
</script>
