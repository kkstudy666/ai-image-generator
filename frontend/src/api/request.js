// 通用 axios 请求封装：自动携带 JWT、统一错误处理、401 自动登出
import axios from 'axios'
import { useAuth } from '../store/auth'

// 后端地址：通过 .env 文件中的 VITE_API_BASE 覆盖（区分开发/生产环境）
const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const request = axios.create({ baseURL: BASE, timeout: 30000 })

// 请求拦截器：自动附带 Authorization 头
request.interceptors.request.use((config) => {
  const { token } = useAuth()
  if (token.value) config.headers.Authorization = `Bearer ${token.value}`
  return config
})

// 响应拦截器：401 时清除本地登录态，其余错误透传
request.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuth().logout()
    }
    return Promise.reject(err)
  }
)

/** 提取后端返回的可读错误信息 */
export function errorMessage(err, fallback = '请求失败') {
  return err.response?.data?.detail || err.message || fallback
}

export { BASE }
export default request
