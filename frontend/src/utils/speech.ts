/** Japanese text-to-speech using Web Speech API with explicit voice selection. */

let _japaneseVoice: SpeechSynthesisVoice | null = null
let _voicesLoaded = false

function _loadVoices(): SpeechSynthesisVoice | null {
  if (_japaneseVoice) return _japaneseVoice

  const voices = window.speechSynthesis.getVoices()
  // Prefer native Microsoft Japanese voice, then any Japanese voice
  _japaneseVoice =
    voices.find(v => v.lang.startsWith('ja') && v.name.includes('Microsoft')) ||
    voices.find(v => v.lang.startsWith('ja')) ||
    null
  _voicesLoaded = true
  return _japaneseVoice
}

/** Speak Japanese text using a proper Japanese TTS voice. */
export function speakJapanese(text: string, rate = 0.85): void {
  // Some browsers load voices asynchronously; listen for the event
  if (!_voicesLoaded) {
    window.speechSynthesis.onvoiceschanged = () => {
      _japaneseVoice = null // reset so _loadVoices re-scans
      _loadVoices()
    }
  }

  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'ja-JP'
  utterance.rate = rate

  const voice = _loadVoices()
  if (voice) {
    utterance.voice = voice
  }

  window.speechSynthesis.speak(utterance)
}
