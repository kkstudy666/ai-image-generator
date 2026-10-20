<template>
  <div class="generator card">
    <h2>生成图片</h2>

    <label>提示词</label>
    <textarea
      v-model="prompt"
      rows="4"
      placeholder="描述你想生成的画面，例如：一只坐在窗边的橘猫，柔和的午后阳光"
    ></textarea>

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
        <input ref="fileInput" type="file" accept="image/*" @change="onPickImage" />
      </div>
    </div>

    <div v-if="imagePreview" class="ref-preview">
      <img :src="imagePreview" alt="参考图预览" />
      <button class="ghost" type="button" @click="clearImage">移除参考图</button>
    </div>

    <button class="primary" :disabled="loading || !prompt.trim()" @click="submit">
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
const inputImage = ref('') // 参考图 data URI
const imagePreview = ref('') // 参考图预览
const fileInput = ref(null)

/** 选择图片后转成 base64 data URI（满足"上传图片转 base64 传给接口"） */
function onPickImage(e) {
  const file = e.target.files[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    alert('图片不能超过 10MB')
    e.target.value = ''
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    inputImage.value = reader.result
    imagePreview.value = reader.result
  }
  reader.readAsDataURL(file)
}

function clearImage() {
  inputImage.value = ''
  imagePreview.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

function submit() {
  if (!prompt.value.trim() || props.loading) return
  emit('submit', {
    prompt: prompt.value.trim(),
    negative_prompt: negativePrompt.value.trim(),
    size: size.value,
    input_image: inputImage.value || null,
  })
}
</script>
