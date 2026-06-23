import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || ''

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,   // Send httpOnly refresh-token cookie on every request
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let _isRefreshing = false
let _pendingQueue = []  // requests queued while a refresh is already in-flight

function _processQueue(error, newToken = null) {
  _pendingQueue.forEach(({ resolve, reject }) =>
    error ? reject(error) : resolve(newToken)
  )
  _pendingQueue = []
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config

    // Only attempt refresh on 401, and never for the /auth/refresh or /auth/login
    // endpoints themselves (would cause an infinite loop).
    const isAuthEndpoint =
      original.url?.includes('/auth/refresh') ||
      original.url?.includes('/auth/login')

    if (error.response?.status === 401 && !original._retried && !isAuthEndpoint) {
      if (_isRefreshing) {
        // Another refresh is already in-flight — queue this request
        return new Promise((resolve, reject) => {
          _pendingQueue.push({ resolve, reject })
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return api(original)
        })
      }

      original._retried = true
      _isRefreshing = true

      try {
        const { data } = await api.post('/auth/refresh')
        const newToken = data.access_token
        localStorage.setItem('token', newToken)
        api.defaults.headers.common.Authorization = `Bearer ${newToken}`
        _processQueue(null, newToken)
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      } catch (refreshError) {
        _processQueue(refreshError, null)
        // Refresh failed — force logout
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        delete api.defaults.headers.common.Authorization
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
        return Promise.reject(refreshError)
      } finally {
        _isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)
