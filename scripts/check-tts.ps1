Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices()
$ja = $v | Where-Object { $_.VoiceInfo.Culture.Name -like "ja*" }
if ($ja) {
    Write-Host "✅ Japanese TTS installed:"
    $ja | ForEach-Object { Write-Host "   Voice: $($_.VoiceInfo.Name)" }
} else {
    Write-Host "❌ No Japanese TTS voice found"
}
