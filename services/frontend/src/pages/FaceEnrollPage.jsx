import { useState, useEffect, useRef, useCallback } from 'react'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { loadModels, detectSingleFace, requestCameraStream } from '../lib/faceRecognition'

export default function FaceEnrollPage() {
  const videoRef = useRef(null)
  const [employees, setEmployees] = useState([])
  const [selectedCode, setSelectedCode] = useState('')
  const [modelsReady, setModelsReady] = useState(false)
  const [cameraOn, setCameraOn] = useState(false)
  const [capturing, setCapturing] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function init() {
      try {
        await loadModels()
        if (cancelled) return
        setModelsReady(true)
        const emps = await api.listEmployees()
        if (cancelled) return
        setEmployees(emps)
        if (emps.length > 0) setSelectedCode(emps[0].employee_code)
      } catch (err) {
        if (!cancelled) setError(`Failed to load: ${err.message}`)
      }
    }
    init()
    return () => { cancelled = true }
  }, [])

  const startCamera = useCallback(async () => {
    try {
      const stream = await requestCameraStream()
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setCameraOn(true)
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  const stopCamera = useCallback(() => {
    const stream = videoRef.current?.srcObject
    if (stream) stream.getTracks().forEach((t) => t.stop())
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setCameraOn(false)
  }, [])

  useEffect(() => {
    return () => stopCamera()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleCapture() {
    if (!videoRef.current || !selectedCode) return
    setCapturing(true)
    setError(null)
    setMessage(null)
    try {
      const detection = await detectSingleFace(videoRef.current)
      if (!detection) {
        setError('No single clear face detected. Make sure only one face is visible and well lit, then try again.')
        return
      }
      await api.enrollFace(selectedCode, Array.from(detection.descriptor))
      setMessage(`Enrolled face for ${selectedCode} successfully.`)
      stopCamera()
    } catch (err) {
      setError(err.message)
    } finally {
      setCapturing(false)
    }
  }

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1>Face Enrollment</h1>
          <p>Capture a reference face for an employee, used for face check-in matching.</p>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      <div className="card" style={{ maxWidth: 480 }}>
        <div className="field">
          <label htmlFor="employee-select">Employee</label>
          <select id="employee-select" value={selectedCode} onChange={(e) => setSelectedCode(e.target.value)}>
            {employees.map((e) => (
              <option key={e.id} value={e.employee_code}>{e.full_name} ({e.employee_code})</option>
            ))}
          </select>
        </div>

        {!modelsReady && <p className="muted">Loading face recognition models…</p>}

        {modelsReady && !cameraOn && (
          <button className="btn btn-primary" onClick={startCamera}>Start Camera</button>
        )}

        {/* The video element is ALWAYS rendered (never conditionally mounted) so that
            videoRef.current exists before startCamera tries to attach a stream to it.
            Conditionally rendering this based on `cameraOn` was the bug: the stream
            got acquired and the camera hardware turned on, but had nowhere to attach
            to, since the <video> tag didn't exist in the DOM yet at that moment. */}
        <div style={{ display: cameraOn ? 'block' : 'none' }}>
          <video
            ref={videoRef}
            style={{ width: '100%', borderRadius: 6, border: '1px solid var(--color-rule-strong)', transform: 'scaleX(-1)' }}
            muted
            playsInline
            autoPlay
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-approve" onClick={handleCapture} disabled={capturing}>
              {capturing ? 'Capturing…' : 'Capture & Enroll'}
            </button>
            <button className="btn btn-secondary" onClick={stopCamera}>Cancel</button>
          </div>
        </div>

        <p className="muted" style={{ marginTop: 16 }}>
          Face directly at the camera in good lighting. One clear frame is captured — no liveness check is
          required for enrollment since this is performed by an HR admin who has already verified the
          employee's identity in person.
        </p>
      </div>
    </Layout>
  )
}