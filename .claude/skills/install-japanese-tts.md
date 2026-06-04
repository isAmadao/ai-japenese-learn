---
name: install-japanese-tts
description: Install Japanese TTS voice pack on Windows so speakJapanese() produces correct Japanese pronunciation
metadata:
  type: skill
  platforms: [windows]
---

# install-japanese-tts

Install Japanese text-to-speech voice pack on Windows, enabling the Web Speech API / `speakJapanese()` to read Japanese text with a proper Japanese accent instead of falling back to Chinese pronunciation.

## Usage

Invoke with:

```
/install-japanese-tts
```

**⚠️ Requires Administrator privileges** for automatic installation.
If the skill runs without admin rights, it will offer manual steps.

To run with admin:
```powershell
# 1. Open PowerShell as Administrator
# 2. Run:
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/install-tts.ps1
```

## What it does

1. Checks if a Japanese TTS voice is already available in the browser
2. If not, offers to install the Microsoft Japanese TTS voice pack via:
   - PowerShell script using the Microsoft Speech API (`Add-WindowsCapability`)
   - Or via Windows Settings UI (fallback)
3. Verifies installation by listing available Japanese voices
4. Restart your browser so the new voice is picked up

## Manual installation (fallback)

If the script fails, manually:

1. Open **Settings → Time & Language → Language & Region**
2. Click **Add a language** → search **日本語** → Install
3. Under **Japanese → Language options → Speech**, download the **Text-to-Speech** voice
4. Restart your browser

## Verification

After installation, run the health check:

```powershell
# PowerShell
Add-Type -AssemblyName System.Speech
$synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synthesizer.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like "ja*" }
```
