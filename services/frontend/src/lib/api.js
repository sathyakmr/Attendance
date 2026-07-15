// Base URLs for each backend service. In local Docker Compose, every
// service publishes its port to the host, and the frontend runs in the
// browser (not inside the compose network) — so it talks to each service
// via localhost:<port>, exactly like the curl examples in the main README.
// For a real deployment, these would move behind a single API gateway
// (see the design doc's architecture) rather than being called directly.
const SERVICES = {
  identity: import.meta.env.VITE_IDENTITY_URL || 'http://localhost:8001',
  attendance: import.meta.env.VITE_ATTENDANCE_URL || 'http://localhost:8000',
  regularization: import.meta.env.VITE_REGULARIZATION_URL || 'http://localhost:8002',
  agent: import.meta.env.VITE_AGENT_URL || 'http://localhost:8003',
  reporting: import.meta.env.VITE_REPORTING_URL || 'http://localhost:8004',
}

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

function getToken() {
  return localStorage.getItem('ams_token')
}

async function request(service, path, { method = 'GET', body, auth = true, apiKey } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth) {
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }
  if (apiKey) headers['X-API-Key'] = apiKey

  const res = await fetch(`${SERVICES[service]}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    localStorage.removeItem('ams_token')
    localStorage.removeItem('ams_role')
    localStorage.removeItem('ams_employee_id')
    localStorage.removeItem('ams_username')
    window.location.href = '/login'
    throw new ApiError('Session expired', 401)
  }

  let data = null
  const text = await res.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!res.ok) {
    const message = (data && data.detail) ? data.detail : `Request failed (${res.status})`
    throw new ApiError(typeof message === 'string' ? message : JSON.stringify(message), res.status)
  }

  return data
}

export const api = {
  // --- identity-service ---
  login: (username, password) =>
    request('identity', '/auth/login', { method: 'POST', body: { username, password }, auth: false }),
  me: () => request('identity', '/auth/me'),

  // --- attendance-service ---
  getEmployee: (employeeCode) => request('attendance', `/api/v1/employees/${employeeCode}`, { auth: false }),
  listEmployees: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request('attendance', `/api/v1/employees${qs ? `?${qs}` : ''}`, { auth: false })
  },
  getAttendanceHistory: (employeeCode, params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request('attendance', `/api/v1/employees/${employeeCode}/attendance${qs ? `?${qs}` : ''}`, { auth: false })
  },
  createEmployee: (payload) =>
    request('attendance', '/api/v1/employees', { method: 'POST', body: payload, auth: false, apiKey: 'dev-local-api-key' }),
  enrollFace: (employeeCode, descriptor) =>
    request('attendance', `/api/v1/employees/${employeeCode}/face-enroll`, {
      method: 'POST',
      body: { descriptor },
      auth: false,
      apiKey: 'dev-local-api-key',
    }),
  listFaceDescriptors: () => request('attendance', '/api/v1/employees/face-descriptors', { auth: false }),
  checkin: (payload) =>
    request('attendance', '/api/v1/checkin', { method: 'POST', body: payload, auth: false, apiKey: 'dev-local-api-key' }),
  getDashboardSummary: () => request('attendance', '/api/v1/dashboard/summary', { auth: false }),
  getLiveAttendance: () => request('attendance', '/api/v1/attendance/live', { auth: false }),
  getAttendanceHistoryTable: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
    ).toString()
    return request('attendance', `/api/v1/attendance/history${qs ? `?${qs}` : ''}`, { auth: false })
  },
  getEmployeeDetailHistory: (employeeCode) =>
    request('attendance', `/api/v1/employees/${employeeCode}/history`, { auth: false }),

  // --- regularization-service ---
  listRegularizations: (statusFilter) =>
    request('regularization', `/api/v1/regularizations${statusFilter ? `?status=${statusFilter}` : ''}`),
  createRegularization: (payload) =>
    request('regularization', '/api/v1/regularizations', { method: 'POST', body: payload }),
  decideRegularization: (requestId, decision, notes) =>
    request('regularization', `/api/v1/regularizations/${requestId}/decision`, {
      method: 'POST',
      body: { decision, notes },
    }),

  // --- ai-agent-service ---
  listReviewQueue: () => request('agent', '/api/v1/agent/review-queue'),
  resolveReviewItem: (itemId, resolution, notes) =>
    request('agent', `/api/v1/agent/review-queue/${itemId}/resolve`, {
      method: 'POST',
      body: { resolution, notes },
    }),
  nlQuery: (question) => request('agent', '/api/v1/agent/query', { method: 'POST', body: { question } }),

  // --- reporting-service ---
  listReports: () => request('reporting', '/api/v1/reports', { auth: false }),
  generateReport: (periodType) =>
    request('reporting', '/api/v1/reports/generate', { method: 'POST', body: { period_type: periodType }, auth: false }),
}

export { ApiError, getToken }
