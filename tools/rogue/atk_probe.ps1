$ErrorActionPreference = 'Continue'
$dir = "D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue"
$libs = Join-Path $dir "Libs"
$handler = [System.ResolveEventHandler] {
    param($s, $e)
    $name = (New-Object System.Reflection.AssemblyName($e.Name)).Name
    foreach ($d in @($dir, $libs)) {
        $p = Join-Path $d "$name.dll"
        if (Test-Path $p) { return [System.Reflection.Assembly]::LoadFrom($p) }
    }
    return $null
}
[System.AppDomain]::CurrentDomain.add_AssemblyResolve($handler)
$asm = [Reflection.Assembly]::LoadFrom((Join-Path $dir "AnvilToolkit.dll"))
Write-Output "loaded: $($asm.FullName)"
$types = @()
try { $types = $asm.GetTypes() } catch { $types = $_.Exception.Types | Where-Object { $_ -ne $null } ; Write-Output "partial types (load errors)" }
$types | Where-Object { $_.Name -match 'Forge|DataFile|Compressed|Compression|Reader|Writer|Codec' } |
    Sort-Object FullName | ForEach-Object { $_.FullName }
