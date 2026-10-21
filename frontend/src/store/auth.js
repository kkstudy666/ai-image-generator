// 用户登录态管理（模块级单例 composable），token 持久化到 localStorage
import { ref, computed } from 'vue'

const TOKEN_KEY = 'aigc_token'
const USER_KEY = 'aigc_user'

// 模块级响应式状态，所有组件共享同一份
const token = ref(localStorage.getItem(TOKEN_KEY) || '')
const user = ref(JSON.parse(localStorage.getItem(USER_KEY) || 'null'))

const isLoggedIn = computed(() => !!token.value)

export function useAuth() {
  /** 登录/注册成功后保存令牌与用户信息 */
  function setAuth(newToken, newUser) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, JSON.stringify(newUser))
  }

  /** 退出登录：清空内存与本地存储 */
  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return { token, user, isLoggedIn, setAuth, logout }
}
