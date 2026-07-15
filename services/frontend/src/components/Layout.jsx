import { NavLink } from 'react-router-dom'
import { useAuth } from '../lib/auth'

const NAV_BY_ROLE = {
  EMPLOYEE: [
    { to: '/employee', label: 'My Attendance' },
  ],
  MANAGER: [
    { to: '/employee', label: 'My Attendance' },
    { to: '/manager', label: 'Team & Approvals' },
    { to: '/reports', label: 'Reports' },
    { to: '/query', label: 'Ask a Question' },
  ],
  HR_ADMIN: [
    { to: '/hr', label: 'Organization' },
    { to: '/hr/face-enroll', label: 'Face Enrollment' },
    { to: '/manager', label: 'Approvals Queue' },
    { to: '/reports', label: 'Reports' },
    { to: '/query', label: 'Ask a Question' },
  ],
  SUPER_ADMIN: [
    { to: '/hr', label: 'Organization' },
    { to: '/hr/face-enroll', label: 'Face Enrollment' },
    { to: '/manager', label: 'Approvals Queue' },
    { to: '/reports', label: 'Reports' },
    { to: '/query', label: 'Ask a Question' },
  ],
}

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const navItems = NAV_BY_ROLE[user?.role] || []

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-brand-mark" />
          Ledger
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? 'active' : '')}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          Signed in as
          <br />
          <span className="role-tag">{user?.username}</span>
          <br />
          {user?.role?.replace('_', ' ')}
          <br />
          <button className="sidebar-logout" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  )
}
