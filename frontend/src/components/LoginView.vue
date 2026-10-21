<template>
  <div class="login card">
    <h2>{{ isRegister ? '注册账号' : '登录' }}</h2>
    <form @submit.prevent="submit">
      <label>用户名</label>
      <input
        v-model.trim="username"
        type="text"
        placeholder="3-32 位字符"
        autocomplete="username"
      />

      <label>密码</label>
      <input
        v-model="password"
        type="password"
        placeholder="至少 6 位"
        autocomplete="current-password"
      />

      <p v-if="error" class="error">{{ error }}</p>

      <button class="primary" type="submit" :disabled="submitting">
        {{ submitting ? '提交中…' : (isRegister ? '注册' : '登录') }}
      </button>
      <button class="ghost" type="button" @click="toggle">
        {{ isRegister ? '已有账号？去登录' : '没有账号？去注册' }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { login, register } from '../api/auth'
import { errorMessage } from '../api/request'
import { useAuth } from '../store/auth'

const emit = defineEmits(['authed'])

const isRegister = ref(false)
const username = ref('')
const password = ref('')
const submitting = ref(false)
const error = ref('')

function toggle() {
  isRegister.value = !isRegister.value
  error.value = ''
}

async function submit() {
  error.value = ''
  if (username.value.length < 3) { error.value = '用户名至少 3 位'; return }
  if (password.value.length < 6) { error.value = '密码至少 6 位'; return }

  submitting.value = true
  try {
    const fn = isRegister.value ? register : login
    const { data } = await fn(username.value, password.value)
    useAuth().setAuth(data.token, data.user)
    emit('authed')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    submitting.value = false
  }
}
</script>
