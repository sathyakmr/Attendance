import { createContext, useContext, useState, useCallback } from 'react'
import { api } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const token = localStorage.getItem('ams_token')
    if (!token) return null
    return {
      token,
      role: localStorage.getItem('ams_role'),
      employeeId: localStorage.getItem('ams_employee_id') || null,
      username: localStorage.getItem('ams_username'),
    }
  })

  const login = useCallback(async (username, password) => {
    const result = await api.login(username, password)
    localStorage.setItem('ams_token', result.access_token)
    localStorage.setItem('ams_role', result.role)
    localStorage.setItem('ams_username', username)
    if (result.employee_id) {
      localStorage.setItem('ams_employee_id', result.employee_id)
    } else {
      localStorage.removeItem('ams_employee_id')
    }
    setUser({ token: result.access_token, role: result.role, employeeId: result.employee_id || null, username })
    return result
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('ams_token')
    localStorage.removeItem('ams_role')
    localStorage.removeItem('ams_employee_id')
    localStorage.removeItem('ams_username')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
