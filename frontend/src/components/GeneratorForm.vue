<template>
  <div class="generator card">
    <h2>生成图片</h2>

    <label>提示词</label>
    <textarea
      v-model="prompt"
      rows="4"
      placeholder="描述你想生成的画面，例如：一只坐在窗边的橘猫，柔和的午后阳光"
    ></textarea>
    <div class="hint">{{ prompt.length }}/2000</div>

    <label>负面提示词（可选）</label>
    <textarea
      v-model="negativePrompt"
      rows="2"
      placeholder="不希望出现的内容，例如：模糊、低质量、水印、多余的手指"
    ></textarea>

    <div class="row">
      <div class="field">
        <label>尺寸</label>
        <select v-model="size">
          <option value="1024x1024">1024 × 1024（方形）</option>
          <option value="1280x720">1280 × 720（横屏）</option>
        </select>
      </div>

      <div class="field">
        <label>参考图（图生图，可选）</label>
        <!-- 点击 + 拖拽上传区域 -->
        <div
          class="dropzone"
          :class="{ over: dragging }"
          @click="fileInput?.click()"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="onDrop"
        >
          <span>{{ imagePreview ? '点击更换参考图' : '点击或拖拽图片到此处（jpg / png / webp，≤10MB）' }}</span>
          <input
            ref="fileInput"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            @change="onPickImage"
          />
        </div>
        <!-- 本地读取进度条 -->
        <div v-if="reading" class="read-progress">
          <div class="bar"><div class="bar-fill" :style="{ width: readPercent + '%' }"></div></div>
          <span class="hint">读取中 {{ readPercent }}%</span>
        </div>
      </div>
    </div>

    <div v-if="imagePreview" class="ref-preview">
      <img :src="imagePreview" alt="参考图预览" />
      <button class="ghost" type="button" @click="clearImage">移除参考图</button>
    </div>

    <p v-if="fileError" class="error">{{ fileError }}</p>

    <button class="primary" :disabled="loading || !prompt.trim() || reading" @click="submit">
      {{ loading ? '生成中…' : '生成图片' }}
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  loading: Boolean, // 是否正在生成，用于禁用按钮
})
const emit = defineEmits(['submit'])

const prompt = ref('')
const negativePrompt = ref('')
const size = ref('1024x1024')
const inputImage = ref('')   // 参考图 data URI
const imagePreview = ref('') // 参考图预览
const fileInput = ref(null)
const dragging = ref(false)  // 拖拽悬停状态
const reading = ref(false)   // 是否正在读取本地文件
const readPercent = ref(0)   // 读取进度
const fileError = ref('')

const MAX_SIZE = 10 * 1024 * 1024
const ALLOWED = ['image/jpeg', 'image/png', 'image/webp']

/** 前端预校验：格式 + 大小（后端还会做文件头校验兜底） */
function validateFile(file) {
  if (!file) return ''
  if (!ALLOWED.includes(file.type)) return '仅支持 jpg / png / webp 格式'
  if (file.size > MAX_SIZE) return '图片大小超过 10MB 上限'
  return ''
}

/** 读取文件为 base64 data URI，并展示读取进度 */
function readFile(file) {
  const err = validateFile(file)
  if (err) { fileError.value = err; return }
  fileError.value = ''
  reading.value = true
  readPercent.value = 0

  const reader = new FileReader()
  reader.onprogress = (e) => {
    if (e.lengthComputable) readPercent.value = Math.round((e.loaded / e.total) * 100)
  }
  reader.onload = () => {
    inputImage.value = reader.result
    imagePreview.value = reader.result
    reading.value = false
  }
  reader.onerror = () => {
    fileError.value = '读取图片失败，请重试'
    reading.value = false
  }
  reader.readAsDataURL(file)
}

function onPickImage(e) {
  const file = e.target.files[0]
  if (file) readFile(file)
  e.target.value = '' // 允许重复选择同一文件
}

function onDrop(e) {
  dragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) readFile(file)
}

function clearImage() {
  inputImage.value = ''
  imagePreview.value = ''
  fileError.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

function submit() {
  if (!prompt.value.trim() || props.loading || reading.value) return
  emit('submit', {
    prompt: prompt.value.trim(),
    negative_prompt: negativePrompt.value.trim(),
    size: size.value,
    input_image: inputImage.value || null,
    // 幂等键：客户端生成 UUID，双击/重试时避免重复生成
    request_id: crypto.randomUUID(),
  })
}
</script>
