# log_watch.ps1 - tails the newest AC.BlackFlag.PatchFix*.log and exits when a notable
# event appears (session handshake / crash / body activity), or after a timeout.
# Usage: powershell -File log_watch.ps1 [-Minutes 20]
param([int]$Minutes = 20)

$dir = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
$seen = @{}
$offsets = @{}
$start = Get-Date
$notable = @()

function Get-NewestLog {
  Get-ChildItem $dir -Filter "AC.BlackFlag.PatchFix*.log" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

"watching $dir ... (up to $Minutes min)"
# seed offsets: only watch NEW lines (a fresh sentinel must not re-trigger on the existing log)
$f0 = Get-NewestLog
if ($f0) { $offsets[$f0.FullName] = $f0.Length }

while (((Get-Date) - $start).TotalMinutes -lt $Minutes) {
  Start-Sleep -Seconds 4
  $f = Get-NewestLog
  if (-not $f) { continue }

  # if the newest log changed, start from 0; else continue from the stored offset
  if (-not $offsets.ContainsKey($f.FullName) -or $f.Length -lt $offsets[$f.FullName]) {
    $offsets[$f.FullName] = 0
  }
  if ($f.Length -le $offsets[$f.FullName]) { continue }

  try {
    $fs = [System.IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite')
    $fs.Seek($offsets[$f.FullName], 'Begin') | Out-Null
    $sr = New-Object System.IO.StreamReader($fs)
    $new = $sr.ReadToEnd()
    $sr.Close(); $fs.Close()
    $offsets[$f.FullName] = $f.Length
  } catch { continue }

  foreach ($line in ($new -split "`r?`n")) {
    if ($line -notmatch "\S") { continue }
    $hit = $false
    if ($line -match "session established|bind udp|critical|VEH:|UNREADABLE|streamed away|body lost|picked body") { $hit = $true }
    if ($line -match "CoopNet: udp/") { $hit = $true }
    if ($line -match "Overlay:") { $hit = $true }
    if ($hit) {
      $key = ($line -replace "^\[[^\]]+\]\s*", "")
      if (-not $seen.ContainsKey($key)) {
        $seen[$key] = $true
        $notable += $line
        Write-Output $line
      }
    }
  }

  # (session-established lines are reported but do not stop the watch; free agents like
  #  re-handshakes during play should not terminate the monitor)
}

"=== EXIT: timeout. Notable lines so far: ==="
$notable | Select-Object -Last 30
