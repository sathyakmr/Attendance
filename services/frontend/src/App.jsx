import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './lib/auth'
import LoginPage from './pages/LoginPage'
import EmployeeDashboard from './pages/EmployeeDashboard'
import ManagerDashboard from './pages/ManagerDashboard'
import HRDashboard from './pages/HRDashboard'
import ReportsPage from './pages/ReportsPage'
import QueryPage from './pages/QueryPage'
import FaceCheckInPage from './pages/FaceCheckInPage'
import FaceEnrollPage from './pages/FaceEnrollPage'

const ROLE_HOME = {
  EMPLOYEE: '/employee',
  MANAGER: '/manager',
  HR_ADMIN: '/hr',
  SUPER_ADMIN: '/hr',
}

function RequireRole({ roles, children }) {
  const { user } = useAuth()
  const location = useLocation()

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  if (roles && !roles.includes(user.role)) {
    return <Navigate to={ROLE_HOME[user.role] || '/login'} replace />
  }
  return children
}

export default function App() {
  const { user } = useAuth()

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/checkin" element={<FaceCheckInPage />} />

      <Route
        path="/employee"
        element={
          <RequireRole roles={['EMPLOYEE', 'MANAGER', 'HR_ADMIN', 'SUPER_ADMIN']}>
            <EmployeeDashboard />
          </RequireRole>
        }
      />
      <Route
        path="/manager"
        element={
          <RequireRole roles={['MANAGER', 'HR_ADMIN', 'SUPER_ADMIN']}>
            <ManagerDashboard />
          </RequireRole>
        }
      />
      <Route
        path="/hr"
        element={
          <RequireRole roles={['HR_ADMIN', 'SUPER_ADMIN']}>
            <HRDashboard />
          </RequireRole>
        }
      />
      <Route
        path="/hr/face-enroll"
        element={
          <RequireRole roles={['HR_ADMIN', 'SUPER_ADMIN']}>
            <FaceEnrollPage />
          </RequireRole>
        }
      />
      <Route
        path="/reports"
        element={
          <RequireRole roles={['MANAGER', 'HR_ADMIN', 'SUPER_ADMIN']}>
            <ReportsPage />
          </RequireRole>
        }
      />
      <Route
        path="/query"
        element={
          <RequireRole roles={['MANAGER', 'HR_ADMIN', 'SUPER_ADMIN']}>
            <QueryPage />
          </RequireRole>
        }
      />

      <Route
        path="/"
        element={<Navigate to={user ? (ROLE_HOME[user.role] || '/login') : '/login'} replace />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
