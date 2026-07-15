import * as faceapi from 'face-api.js'

/**
 * Requests camera access with clear, specific diagnostics for every common
 * failure mode — getUserMedia's native errors are terse (e.g. "Permission
 * denied") and don't explain *why*, which makes camera issues hard to
 * self-diagnose. This translates them into actionable messages.
 */
export async function requestCameraStream(constraints = { video: { width: 480, height: 360 } }) {
  if (!window.isSecureContext) {
    throw new Error(
      'Camera access requires a secure context (HTTPS, or exactly "http://localhost"). ' +
      `You're currently on "${window.location.origin}" — if that's a LAN IP address, a different ` +
      'hostname, or plain HTTP on a non-localhost domain, browsers block camera access entirely, ' +
      'often without even showing a permission prompt. Access this app via http://localhost:3000 instead.'
    )
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error(
      'This browser does not expose the camera API (navigator.mediaDevices.getUserMedia is unavailable). ' +
      'Try a recent version of Chrome, Firefox, or Edge.'
    )
  }

  try {
    return await navigator.mediaDevices.getUserMedia(constraints)
  } catch (err) {
    switch (err.name) {
      case 'NotAllowedError':
      case 'PermissionDeniedError':
        throw new Error(
          'Camera permission was denied. Check the camera icon in your browser\'s address bar, or your ' +
          'OS-level camera privacy settings (System Settings → Privacy → Camera on Mac; Settings → ' +
          'Privacy → Camera on Windows), and make sure this browser is allowed.'
        )
      case 'NotFoundError':
      case 'DevicesNotFoundError':
        throw new Error('No camera device was found on this machine. Plug in a webcam, or check it isn\'t disabled.')
      case 'NotReadableError':
      case 'TrackStartError':
        throw new Error('The camera is already in use by another application or browser tab. Close it and try again.')
      case 'OverconstrainedError':
      case 'ConstraintNotSatisfiedError':
        throw new Error('Your camera doesn\'t support the requested resolution. Try a different camera, or this needs a code adjustment to relax the constraints.')
      case 'SecurityError':
        throw new Error('Camera access was blocked by browser security policy (e.g. an iframe without camera permission).')
      default:
        throw new Error(`Camera access failed (${err.name || 'unknown error'}): ${err.message}`)
    }
  }
}

let modelsLoaded = false

export async function loadModels() {
  if (modelsLoaded) return
  const MODEL_URL = '/models'
  await Promise.all([
    faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
    faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
    faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
  ])
  modelsLoaded = true
}

const DETECTOR_OPTIONS = new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 })

/**
 * Runs detection + landmarks + descriptor extraction on a single video frame.
 * Returns null if no face (or more than one face) is found — check-in
 * requires exactly one clearly detected face.
 */
export async function detectSingleFace(videoEl) {
  const results = await faceapi
    .detectAllFaces(videoEl, DETECTOR_OPTIONS)
    .withFaceLandmarks()
    .withFaceDescriptors()

  if (results.length !== 1) return null
  return results[0]
}

/** Euclidean distance between two 128-d descriptors. Lower = more similar. */
export function descriptorDistance(a, b) {
  let sum = 0
  for (let i = 0; i < a.length; i++) {
    const d = a[i] - b[i]
    sum += d * d
  }
  return Math.sqrt(sum)
}

// face-api.js's own docs suggest ~0.6 as a typical match threshold for this
// recognition model. Lower = stricter (fewer false accepts, more false
// rejects). This is a coarse, tunable default — a real deployment should
// calibrate this against actual enrollment photos before relying on it.
export const MATCH_THRESHOLD = 0.55

/**
 * 1:N match against every enrolled descriptor. Returns the best match if
 * it's under MATCH_THRESHOLD, else null (no confident match).
 */
export function findBestMatch(liveDescriptor, enrolledEmployees) {
  let best = null
  let bestDistance = Infinity
  for (const emp of enrolledEmployees) {
    const distance = descriptorDistance(liveDescriptor, emp.descriptor)
    if (distance < bestDistance) {
      bestDistance = distance
      best = emp
    }
  }
  if (best && bestDistance < MATCH_THRESHOLD) {
    return { employee: best, distance: bestDistance }
  }
  return null
}

// --- Liveness: blink detection via Eye Aspect Ratio (EAR) ---
//
// This is a lightweight, real, client-side liveness signal — not a
// commercial-grade anti-spoofing system. It computes the eye-aspect-ratio
// from the 68-point landmarks each frame and looks for a genuine
// open -> closed -> open transition within the capture window. A printed
// photo or a static image held up to the camera cannot produce this
// transition, which is the specific spoofing vector this defends against.
// It does NOT defend against a video replay of the enrolled person blinking,
// which is a known limitation of blink-based liveness in general — flagged
// explicitly in the README rather than glossed over.

function eyeAspectRatio(eyePoints) {
  // eyePoints: 6 landmark points around one eye, in face-api.js's standard order
  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y)
  const vertical1 = dist(eyePoints[1], eyePoints[5])
  const vertical2 = dist(eyePoints[2], eyePoints[4])
  const horizontal = dist(eyePoints[0], eyePoints[3])
  return (vertical1 + vertical2) / (2.0 * horizontal)
}

export function averageEAR(landmarks) {
  const leftEAR = eyeAspectRatio(landmarks.getLeftEye())
  const rightEAR = eyeAspectRatio(landmarks.getRightEye())
  return (leftEAR + rightEAR) / 2
}

export const EAR_BLINK_THRESHOLD = 0.24 // below this = eyes considered closed

/**
 * Tracks a sequence of EAR readings and reports whether a genuine blink
 * (open -> closed -> open) has occurred within the buffer.
 */
export class BlinkDetector {
  constructor() {
    this.history = []
    this.sawClosed = false
    this.blinkDetected = false
  }

  addReading(ear) {
    this.history.push(ear)
    if (this.history.length > 30) this.history.shift()

    if (ear < EAR_BLINK_THRESHOLD) {
      this.sawClosed = true
    } else if (this.sawClosed && ear >= EAR_BLINK_THRESHOLD) {
      // transitioned back to open after having been closed — that's a blink
      this.blinkDetected = true
      this.sawClosed = false
    }
  }

  hasBlinked() {
    return this.blinkDetected
  }

  reset() {
    this.history = []
    this.sawClosed = false
    this.blinkDetected = false
  }
}