import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import {
  loadModels,
  detectSingleFace,
  findBestMatch,
  averageEAR,
  BlinkDetector,
  requestCameraStream,
} from '../lib/faceRecognition'

const STAGE = {
  LOADING_MODELS: 'LOADING_MODELS',
  READY: 'READY',
  AWAITING_BLINK: 'AWAITING_BLINK',
  MATCHING: 'MATCHING',
  RESULT: 'RESULT',
  ERROR: 'ERROR',
}

export default function FaceCheckInPage() {
  const videoRef = useRef(null)
  const blinkDetectorRef = useRef(new BlinkDetector())
  const intervalRef = useRef(null)

  const [stage, setStage] = useState(STAGE.LOADING_MODELS)
  const [error, setError] = useState(null)
  const [enrolledEmployees, setEnrolledEmployees] = useState([])
  const [result, setResult] = useState(null)
  const [eventType, setEventType] = useState('CHECK_IN')

  useEffect(() => {
    let cancelled = false
    async function init() {
      try {
        await loadModels()
        const descriptors = await api.listFaceDescriptors()
        if (cancelled) return
        setEnrolledEmployees(descriptors)
        setStage(STAGE.READY)
      } catch (err) {
        if (!cancelled) {
          setError(`Could not load face recognition models or enrolled employees: ${err.message}`)
          setStage(STAGE.ERROR)
        }
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
      blinkDetectorRef.current.reset()
      setStage(STAGE.AWAITING_BLINK)
      setError(null)
    } catch (err) {
      setError(err.message)
      setStage(STAGE.ERROR)
    }
  }, [])

  const stopCamera = useCallback(() => {
    const stream = videoRef.current?.srcObject
    if (stream) {
      stream.getTracks().forEach((t) => t.stop())
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  // Safety net: release the camera if the user navigates away mid-session
  // (e.g. clicking "Staff login" while the camera is still running), not
  // just when the normal stopCamera() call sites are reached.
  useEffect(() => {
    return () => stopCamera()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (stage !== STAGE.AWAITING_BLINK) return

    intervalRef.current = setInterval(async () => {
      if (!videoRef.current) return
      const detection = await detectSingleFace(videoRef.current)
      if (!detection) return // no face, or more than one — keep waiting

      const ear = averageEAR(detection.landmarks)
      blinkDetectorRef.current.addReading(ear)

      if (blinkDetectorRef.current.hasBlinked()) {
        clearInterval(intervalRef.current)
        setStage(STAGE.MATCHING)
        await performMatch(detection.descriptor)
      }
    }, 200)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage])

  async function performMatch(descriptor) {
    const match = findBestMatch(descriptor, enrolledEmployees)
    stopCamera()

    if (!match) {
      setResult({ success: false, message: 'No confident match found. Please try again, or contact HR if you have not been enrolled.' })
      setStage(STAGE.RESULT)
      return
    }

    try {
      const event = await api.checkin({
        employee_code: match.employee.employee_code,
        event_type: eventType,
        source: 'BIOMETRIC',
      })
      setResult({
        success: true,
        employeeName: match.employee.full_name,
        distance: match.distance,
        event,
      })
    } catch (err) {
      setResult({ success: false, message: err.message, employeeName: match.employee.full_name })
    }
    setStage(STAGE.RESULT)
  }

  function reset() {
    setResult(null)
    setStage(STAGE.READY)
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={{ textAlign: 'center' }}>Face Check-In</h1>
        <p className="muted" style={{ textAlign: 'center', marginBottom: 20 }}>
          Look at the camera and blink naturally to confirm you're really there.
        </p>

        {stage === STAGE.LOADING_MODELS && <div className="empty-state">Loading face recognition models…</div>}

        {stage === STAGE.ERROR && (
          <div>
            <div className="error-banner">{error}</div>
            <button className="btn btn-secondary" style={{ width: '100%', justifyContent: 'center', marginTop: 12 }} onClick={() => setStage(STAGE.READY)}>
              Try Again
            </button>
          </div>
        )}

        {stage === STAGE.READY && (
          <>
            <div className="field">
              <label htmlFor="event-type">Action</label>
              <select id="event-type" value={eventType} onChange={(e) => setEventType(e.target.value)}>
                <option value="CHECK_IN">Check In</option>
                <option value="CHECK_OUT">Check Out</option>
              </select>
            </div>
            <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={startCamera}>
              Start Camera
            </button>
            {enrolledEmployees.length === 0 && (
              <p className="muted" style={{ marginTop: 12 }}>
                No employees are enrolled for face recognition yet. An HR admin can enroll employees from the Organization page.
              </p>
            )}
          </>
        )}

        {/* The video element is ALWAYS rendered (never conditionally mounted) so that
            videoRef.current exists before startCamera tries to attach a stream to it.
            Conditionally rendering this based on `stage` was the bug: the stream got
            acquired and the camera hardware turned on, but had nowhere to attach to,
            since the <video> tag didn't exist in the DOM yet at that moment. */}
        <div style={{ display: (stage === STAGE.AWAITING_BLINK || stage === STAGE.MATCHING) ? 'block' : 'none' }}>
          <video ref={videoRef} style={styles.video} muted playsInline autoPlay />
          <p className="muted" style={{ textAlign: 'center', marginTop: 12 }}>
            {stage === STAGE.AWAITING_BLINK ? 'Looking for a face… blink to confirm liveness.' : 'Matching…'}
          </p>
        </div>

        {stage === STAGE.RESULT && result && (
          <div>
            {result.success ? (
              <div className="success-banner">
                Welcome, {result.employeeName}. {eventType === 'CHECK_IN' ? 'Checked in' : 'Checked out'} successfully
                {' '}(match confidence: {(1 - result.distance).toFixed(2)}).
              </div>
            ) : (
              <div className="error-banner">
                {result.employeeName ? `Matched ${result.employeeName}, but: ` : ''}{result.message}
              </div>
            )}
            <button className="btn btn-secondary" style={{ width: '100%', justifyContent: 'center', marginTop: 12 }} onClick={reset}>
              Check In Someone Else
            </button>
          </div>
        )}

        <p className="muted" style={{ textAlign: 'center', marginTop: 24 }}>
          <Link to="/login">Staff login</Link>
        </p>
      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--color-ink)',
  },
  card: {
    background: 'var(--color-paper-raised)',
    padding: '40px 36px',
    borderRadius: 8,
    width: 440,
    boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
  },
  video: {
    width: '100%',
    borderRadius: 6,
    border: '1px solid var(--color-rule-strong)',
    transform: 'scaleX(-1)',
  },
}