/** Japanese text-to-speech.
 *
 *  Strategy (tried in order):
 *    1. Web Speech API (built-in browser TTS — best quality, zero network)
 *       → tries with Japanese voice, then falls back to lang=ja-JP (works
 *         on iOS Safari, and on Android Chrome with cloud TTS)
 *       → detects broken stubs (accept speak() silently but produce no
 *         audio) by checking if onend fires suspiciously fast (< 500ms)
 *    2. Server-side TTS via /api/tts (Microsoft Edge TTS)
 *       → reuses a hidden <audio> element in the DOM so mobile autoplay
 *         policies don't block playback after the async fetch
 */

let _japaneseVoice: SpeechSynthesisVoice | null = null
let _voicesLoaded = false
let _voicesLoading = false

/** Hidden <audio> reused for server TTS — keeps autoplay working on mobile. */
let _serverAudio: HTMLAudioElement | null = null
/** Previous blob URL — revoked before setting a new one to avoid leaks. */
let _previousBlobUrl: string | null = null

function _scanVoices(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null

  _japaneseVoice =
    voices.find(v => v.lang.startsWith('ja') && /microsoft|google/.test(v.name.toLowerCase())) ||
    voices.find(v => v.lang.startsWith('ja')) ||
    null
  _voicesLoaded = true
  _voicesLoading = false
  return _japaneseVoice
}

/** Ensure voices are loaded (Chrome loads them async). */
function _ensureVoices(): void {
  if (_voicesLoaded || _voicesLoading) return
  const voices = window.speechSynthesis.getVoices()
  if (voices.length) {
    _scanVoices()
    return
  }
  // Chrome: voices load async, need the event
  _voicesLoading = true
  window.speechSynthesis.onvoiceschanged = () => {
    _scanVoices()
  }
}

/** Try local speech via Web Speech API.
 *
 *  Returns true ONLY if the browser actually produces audio.
 *
 *  Stub detection (browsers that accept speak() but produce no sound):
 *  1. After 1500ms, if `speechSynthesis.speaking` is still false, the
 *     browser's engine never started → treat as broken.
 *  2. If `onend` fires in under 500ms, the engine finished suspiciously
 *     fast with no actual audio → treat as broken.
 *
 *  When the engine IS working, we wait for natural onend — no artificial
 *  timeout, so no false fallback that causes overlapping audio.
 */
function _speakLocal(text: string, rate: number): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      resolve(false)
      return
    }

    _ensureVoices()
    window.speechSynthesis.cancel()

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'ja-JP'
    utterance.rate = rate
    if (_japaneseVoice) utterance.voice = _japaneseVoice

    let didResolve = false
    const t0 = performance.now()
    const done = (ok: boolean) => {
      if (!didResolve) { didResolve = true; resolve(ok) }
    }

    utterance.onend = () => {
      // If the utterance "finished" in < 500ms, it's a broken stub that
      // fires onend immediately without producing audio.
      done(performance.now() - t0 >= 500)
    }
    utterance.onerror = () => done(false)

    window.speechSynthesis.speak(utterance)

    // After a generous delay, check if the engine ever started speaking.
    // Some mobile browsers accept speak() but never start the engine.
    setTimeout(() => {
      if (!didResolve) {
        if (!window.speechSynthesis.speaking) {
          done(false) // broken stub or too slow to start
        }
        // else: engine is active — wait for natural onend/onerror
      }
    }, 1500)
  })
}

/** Speak via backend TTS endpoint.
 *
 *  Uses a hidden, reusable <audio> element in the DOM. On mobile,
 *  DOM-attached audio elements are less likely to be blocked by autoplay
 *  policies than ephemeral `new Audio()` objects.
 */
async function _speakServer(text: string): Promise<boolean> {
  try {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    if (!res.ok) return false

    const blob = await res.blob()
    const url = URL.createObjectURL(blob)

    // Create (or reuse) a hidden <audio> in the DOM — keeps mobile
    // autoplay happy after the async fetch completes.
    // Revoke previous blob URL before setting a new one
    if (_previousBlobUrl) {
      URL.revokeObjectURL(_previousBlobUrl)
    }
    _previousBlobUrl = url

    if (!_serverAudio) {
      _serverAudio = document.createElement('audio')
      _serverAudio.setAttribute('playsinline', '')
      _serverAudio.style.display = 'none'
      document.body.appendChild(_serverAudio)
    }
    _serverAudio.src = url

    return new Promise((resolve) => {
      let didResolve = false
      const done = (ok: boolean) => {
        if (!didResolve) {
          didResolve = true
          URL.revokeObjectURL(url)
          resolve(ok)
        }
      }

      _serverAudio!.onended = () => done(true)
      _serverAudio!.onerror = () => done(false)
      _serverAudio!.play().catch(() => done(false))
    })
  } catch {
    return false
  }
}

/** Monotonic sequence counter for speakJapanese.
 *  Incremented on every call. When a newer call cancels an older call's
 *  utterance (via _speakLocal's internal cancel()), the older call's
 *  _speakLocal resolves to false — without this guard the old call
 *  would then trigger the server fallback, producing overlapping audio.
 */
let _speakSeq = 0

/** Stop any ongoing speech immediately.
 *
 *  Call this in ``onUnmounted`` of any component that uses ``speakJapanese``
 *  to prevent audio from continuing after navigation.
 */
export function stopSpeech(): void {
  _speakSeq++  // invalidate any in-flight promise chain

  // Stop browser-native speech
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }

  // Stop server-side <audio>
  if (_serverAudio) {
    _serverAudio.pause()
    _serverAudio.currentTime = 0
  }
}

/** Speak Japanese text.
 *  Safe to call rapidly — each call cancels the previous utterance.
 */
export async function speakJapanese(text: string, rate = 0.85): Promise<void> {
  const seq = ++_speakSeq
  const localOk = await _speakLocal(text, rate)
  if (seq !== _speakSeq) return // superseded by a newer click — discard
  if (localOk) return

  // Fallback to server-side TTS
  await _speakServer(text)
}
