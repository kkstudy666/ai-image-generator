<template>
  <div class="gallery card">
    <h2>作品画廊</h2>
    <p v-if="items.length === 0 && !loading" class="empty">暂无作品，快去生成第一张图片吧</p>

    <div class="grid">
      <div v-for="item in items" :key="item.task_id" class="grid-item">
        <!-- loading="lazy" 实现图片懒加载 -->
        <img
          v-if="(item.local_path || item.image_url) && !item._imgError"
          :src="imageUrl(item.task_id)"
          :alt="item.prompt"
          loading="lazy"
          title="点击预览"
          @click="$emit('preview', item)"
          @error="item._imgError = true"
        />
        <div v-else class="placeholder">{{ statusText(item.status) }}</div>
        <div class="meta">
          <p class="prompt">{{ item.prompt }}</p>
          <p class="time">{{ item.created_at }} · {{ statusText(item.status) }}</p>
        </div>
      </div>
    </div>

    <!-- 底部哨兵：滚动接近时触发加载更多 -->
    <div ref="sentinel" class="load-more">
      <span v-if="loading">加载中…</span>
      <span v-else-if="hasMore">向下滚动加载更多</span>
      <span v-else-if="items.length > 0">已加载全部</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { imageUrl } from '../api/generate'

const props = defineProps({
  items: { type: Array, default: () => [] },
  loading: Boolean, // 是否正在加载更多
  hasMore: Boolean, // 是否还有更多数据
})
const emit = defineEmits(['preview', 'load-more'])

const STATUS_TEXT = {
  queued: '排队中',
  generating: '生成中',
  retrying: '重试中',
  success: '成功',
  failed: '失败',
}
function statusText(s) { return STATUS_TEXT[s] || s }

// IntersectionObserver 监听底部哨兵，滚动分页加载
const sentinel = ref(null)
let observer = null

onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && props.hasMore && !props.loading) {
        emit('load-more')
      }
    },
    { rootMargin: '200px' }
  )
  if (sentinel.value) observer.observe(sentinel.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
})
</script>
