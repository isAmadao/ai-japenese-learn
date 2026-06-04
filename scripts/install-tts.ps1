<#
.SYNOPSIS
    Install Japanese TTS voice pack on Windows 10/11
.DESCRIPTION
    Checks for existing Japanese TTS voices, and if missing, attempts to install
    via the Windows Speech API capability package. Falls back to guidance for
    manual installation.
#>

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Japanese TTS Installation"

# ── Check admin ───────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "⚠  This script needs Administrator privileges to install TTS voices." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   Run as Administrator:" -ForegroundColor Cyan
    Write-Host "   Start → 'PowerShell' → right-click → Run as Administrator" -ForegroundColor White
    Write-Host "   cd $PSScriptRoot" -ForegroundColor Gray
    Write-Host "   .\install-tts.ps1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   Or via Claude Code:" -ForegroundColor Cyan
    Write-Host '   !powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install-tts.ps1' -ForegroundColor Gray
    Write-Host ""
    Write-Host "   Running detection-only mode (no install will be attempted)..." -ForegroundColor Gray
    Write-Host ""
}

# ── 1. Check existing voices ──────────────────────────────
Write-Host "🔍 Checking installed TTS voices..." -ForegroundColor Cyan

Add-Type -AssemblyName System.Speech
$synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = $synthesizer.GetInstalledVoices()

$jaVoices = $voices | Where-Object { $_.VoiceInfo.Culture.Name -like "ja*" }

if ($jaVoices) {
    Write-Host "✅ Japanese TTS voices already installed:" -ForegroundColor Green
    $jaVoices | ForEach-Object {
        $v = $_.VoiceInfo
        Write-Host "   • $($v.Name) ($($v.Culture.Name))" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "📝 If your browser still speaks Chinese, restart it." -ForegroundColor Yellow
    exit 0
}

Write-Host "⚠  No Japanese TTS voice found." -ForegroundColor Yellow

# ── 2. Attempt automatic install ──────────────────────────
Write-Host "`n📦 Attempting to install Microsoft Japanese TTS voice..." -ForegroundColor Cyan

$capabilities = @(
    "Language.Speech~~~ja-JP~0.0.1.0"   # Windows 10/11 Japanese Speech
    "Language.Basic~~~ja-JP~0.0.1.0"     # Basic Japanese language support
)

foreach ($cap in $capabilities) {
    Write-Host "   Installing $cap ..." -ForegroundColor Gray
    try {
        $result = Add-WindowsCapability -Online -Name $cap -ErrorAction SilentlyContinue
        if ($result.RestartNeeded) {
            Write-Host "   ⚠  Restart needed" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "   ⚠  Failed: $_" -ForegroundColor Yellow
    }
}

# ── 3. Verify ──────────────────────────────────────────────
Write-Host "`n🔍 Re-checking voices..." -ForegroundColor Cyan
Start-Sleep -Seconds 2

$synthesizer2 = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices2 = $synthesizer2.GetInstalledVoices()
$jaVoices2 = $voices2 | Where-Object { $_.VoiceInfo.Culture.Name -like "ja*" }

if ($jaVoices2) {
    Write-Host "✅ Japanese TTS installed successfully:" -ForegroundColor Green
    $jaVoices2 | ForEach-Object {
        Write-Host "   • $($_.VoiceInfo.Name)" -ForegroundColor Green
    }
} else {
    Write-Host "`n❌ Automatic installation failed." -ForegroundColor Red
    Write-Host "`n📋 Manual installation:" -ForegroundColor Yellow
    Write-Host "   1. Open Settings → Time & Language → Language & Region"
    Write-Host "   2. Add a language → 日本語 → Next → Install"
    Write-Host "   3. After install, open Japanese → Language options"
    Write-Host "   4. Download 'Text-to-Speech' under Speech"
    Write-Host "   5. Restart your computer and browser"
    Write-Host "`n   Or run directly:" -ForegroundColor Gray
    Write-Host "   ms-settings:regionlanguage" -ForegroundColor Gray
}

Write-Host "`n🔄 Restart your browser after installation." -ForegroundColor Cyan
