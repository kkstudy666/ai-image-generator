import request from './request'

/** 用户注册 */
export function register(username, password) {
  return request.post('/api/auth/register', { username, password })
}

/** 用户登录 */
export function login(username, password) {
  return request.post('/api/auth/login', { username, password })
}
