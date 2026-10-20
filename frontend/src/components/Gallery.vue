<template>
  <div class="gallery card">
    <h2>作品画廊</h2>
    <p v-if="items.length === 0" class="empty">暂无作品，快去生成第一张图片吧</p>
    <div class="grid">
      <div v-for="item in items" :key="item.task_id" class="grid-item">
        <!-- 图片默认支持右键「图片另存为」保存下载 -->
        <img
          v-if="item.image_url"
          :src="item.image_url"
          :alt="item.prompt"
          title="点击预览，右键可保存图片"
          @click="$emit('preview', item)"
        />
        <div v-else class="placeholder">{{ statusText(item.status) }}</div>
        <div class="meta">
          <p class="prompt">{{ item.prompt }}</p>
          <p class="time">{{ item.created_at }} · {{ statusText(item.status) }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
})
defineEmits(['preview'])

const STATUS_TEXT = {
  queued: '排队中',
  generating: '生成中',
  success: '成功',
  failed: '失败',
}
function statusText(s) {
  return STATUS_TEXT[s] || s
}
</script>
