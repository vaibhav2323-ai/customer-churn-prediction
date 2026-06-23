import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../utils/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // Restore session from localStorage on mount
  useEffect(() => {
    const token = localStorage.getItem('token')
    const stored = localStorage.getItem('user')
    if (token && stored) {
      try {
        api.defaults.headers.common.Authorization = `Bearer ${token}`
        setUser(JSON.parse(stored))
      } catch {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
      }
    }
    setLoading(false)
  }, [])

  const login = async (email, password) => {
    // withCredentials=true (set on the axios instance) means the httpOnly
    // refresh-token cookie returned by the server is stored automatically.
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`
    setUser(data.user)
    return data
  }

  const register = async (email, password, full_name) => {
    const { data } = await api.post('/auth/register', { email, password, full_name })
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`
    setUser(data.user)
    return data
  }

  const logout = async () => {
    try {
      // Tell the server to revoke the refresh token and clear the cookie
      await api.post('/auth/logout')
    } catch {
      // Ignore network errors — we still clear local state
    } finally {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      delete api.defaults.headers.common.Authorization
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
