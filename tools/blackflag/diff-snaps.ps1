param([Parameter(Mandatory=$true)][string]$A, [Parameter(Mandatory=$true)][string]$B)
$dir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs"
$fa = Join-Path $dir ("snap-" + $A + ".txt")
$fb = Join-Path $dir ("snap-" + $B + ".txt")
if (-not (Test-Path $fa) -or -not (Test-Path $fb)) { "missing snapshots"; exit }
$la = Get-Content $fa
$lb = Get-Content $fb
$mapB = @{}
foreach ($l in $lb) { if ($l.Length -gt 20) { $mapB[$l.Substring(0,20)] = $l } }
$diffCount = 0
"--- differences (A=" + $A + "  B=" + $B + ") ---"
foreach ($l in $la) {
  if ($l.Length -le 20) { continue }
  $key = $l.Substring(0,20)
  if (-not $mapB.ContainsKey($key)) { continue }
  $other = $mapB[$key]
  if ($other -ne $l) {
    $diffCount++
    "A " + $l
    "B " + $other
  }
}
"total differing lines: $diffCount"