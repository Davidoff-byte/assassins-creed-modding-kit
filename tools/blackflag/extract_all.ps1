$bms = "C:\Users\Administrator\Documents\Default Project\bf-coop\tools\bms"
$game = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"
$root = "D:\bf4_extract"
$done = @("DataPC_extra_chr.forge", "DataPC_Havana.forge", "DataPC_CaribbeanSea.forge")
$nl = ("`n" * 100000)

$files = @()
$files += Get-ChildItem $game -Filter "*.forge" -File | Select-Object -ExpandProperty FullName
$files += Get-ChildItem "$game\multi" -Filter "*.forge" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
$files += Get-ChildItem "$game\dlc_*" -Filter "*.forge" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName

foreach ($f in $files) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($f)
    if ($done -contains [System.IO.Path]::GetFileName($f)) { continue }
    $out = Join-Path $root $name
    if (Test-Path $out) { continue }
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    Write-Host ("=== extracting " + [System.IO.Path]::GetFileName($f) + " ===")
    $nl | & "$bms\quickbms\quickbms.exe" -o "$bms\scimitar_alt.bms" $f $out *>&1 | Select-String -Pattern "files found" | ForEach-Object { $_.Line }
}
Write-Host "ALL DONE"
