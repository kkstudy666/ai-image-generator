<template>
  <div v-if="status" class="progress card">
    <div class="progress-head">
      <span class="dot" :class="status"></span>
      <span class="progress-text">{{ statusText(status) }}</span>
      <span v-if="error" class="error">（{{ error }}）</span>
    </div>

    <!-- 进度条动画：生成中呈呼吸/推进效果 -->
    <div class="bar">
      <div class="bar-fill" :class="status" :style="{ width: percent + '%' }"></div>
    </div>

    <!-- 失败重试按钮 -->
    <button v-if="status === 'failed'" class="retry" type="button" @click="$emit('retry')">
      重试
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: '' }, // queued / generating / retrying / success / failed
  error: { type: String, default: '' },
})
defineEmits(['retry'])

const STATUS_TEXT = {
  queued: '排队中',
  generating: '生成中',
  retrying: '重试中',
  success: '生成成功',
  failed: '生成失败',
}
function statusText(s) { return STATUS_TEXT[s] || s }

// 不同状态对应不同进度宽度，配合 CSS transition 呈现动画
const percent = computed(() => {
  switch (props.status) {
    case 'queued': return 20
    case 'generating': return 70
    case 'retrying': return 50
    case 'success': return 100
    case 'failed': return 100
    default: return 0
  }
})
</script>
