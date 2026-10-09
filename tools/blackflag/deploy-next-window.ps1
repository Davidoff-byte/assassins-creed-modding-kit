# deploy-next-window.ps1 - run when the game is CLOSED.
$src = "C:\Users\Administrator\Documents\Default Project\ac-rogue\AC.PatchFix\build-x86\bin\Release\AC.BlackFlag.PatchFix.asi"
$dst = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins\AC.BlackFlag.PatchFix.asi"
$ini = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins\AC.BlackFlag.PatchFix.ini"

$g = Get-Process AC4BFSP -ErrorAction SilentlyContinue
if ($g) { Write-Host "GAME IS RUNNING - close it first"; exit 1 }

Copy-Item $dst "$dst.bak_$(Get-Date -Format 'MMdd_HHmmss')" -Force
Copy-Item $src $dst -Force
Write-Host "deployed:" (Get-FileHash $dst -Algorithm MD5).Hash

# desired ini state for the test window
$txt = [System.IO.File]::ReadAllText($ini, [System.Text.Encoding]::UTF8)
foreach ($kv in @(@("SpawnTest", "false"), @("SpawnWatch", "true"), @("NavTest", "false"),
                  @("NavWatch", "true"), @("CloneLive", "false"), @("AnimDrive", "false"),
                  @("AnimProbe", "false"), @("CombatSync", "true"))) {
  if ($txt -match ("(?m)^" + $kv[0] + "=")) { $txt = $txt -replace ("(?m)^" + $kv[0] + "=.*$"), ($kv[0] + "=" + $kv[1]) }
  else { $txt = $txt + "`r`n" + $kv[0] + "=" + $kv[1] }
}
[System.IO.File]::WriteAllText($ini, $txt, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "ini preset for the test window done"
