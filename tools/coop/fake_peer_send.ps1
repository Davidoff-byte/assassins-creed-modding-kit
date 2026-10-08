param([int]$DurationSec = 120, [int]$PluginPort = 27810, [int]$ListenPort = 27811, [double]$Radius = 2.5)

# Fake co-op peer: sends AccCoop Player packets to the BlackFlag plugin (as client 2),
# circling the local player, and listens for the plugin's own publishes on the peer port.
# Packet = Envelope(16) + PlayerPayload(56) = 72 bytes, little-endian.

$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit 1 }
$pidG = $p.Id
"game pid = $pidG"
"fake peer: sending to 127.0.0.1:$PluginPort as client 2; listening on $ListenPort; radius $Radius"

Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class FP {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
$h = [FP]::OpenProcess(0x0410, $false, $pidG)
function GetMem([int64]$a, [int]$n) { $b = New-Object byte[] $n; $r = [IntPtr]::Zero; [void][FP]::ReadProcessMemory($h, [IntPtr]$a, $b, $n, [ref]$r); return $b }
function GetU32([int64]$a) { return [BitConverter]::ToUInt32((GetMem $a 4), 0) }

function GetPlayerFeet {
  $mgr = GetU32 0x2ABE588
  if ($mgr -eq 0) { return $null }
  $holder = GetU32 ($mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = GetU32 $holder; if ($camobj -eq 0) { return $null }
  $block = GetU32 ($camobj + 0x68); if ($block -eq 0) { return $null }
  $prov = GetU32 ($block + 0x174); if ($prov -eq 0) { return $null }
  $b = GetMem ($prov + 0x110) 12
  return [pscustomobject]@{ x = [BitConverter]::ToSingle($b,0); y = [BitConverter]::ToSingle($b,4); z = [BitConverter]::ToSingle($b,8) }
}

function BuildPacket([uint32]$seq, [single]$px, [single]$py, [single]$pz, [single]$qx, [single]$qy, [single]$qz, [single]$qw, [uint32]$ms) {
  $ms_ = New-Object System.IO.MemoryStream
  $bw = New-Object System.IO.BinaryWriter($ms_)
  $bw.Write([uint32]0x50524341)
  $bw.Write([uint16]1)
  $bw.Write([uint16]1)
  $bw.Write([uint32]$seq)
  $bw.Write([uint32]2)
  $bw.Write([single]$px); $bw.Write([single]$py); $bw.Write([single]$pz)
  $bw.Write([single]$qx); $bw.Write([single]$qy); $bw.Write([single]$qz); $bw.Write([single]$qw)
  $bw.Write([single]0); $bw.Write([single]0); $bw.Write([single]0)
  $bw.Write([single]100)
  $bw.Write([uint32]0)
  $bw.Write([uint32]$ms)
  $bw.Write([uint32]0)
  $bw.Flush()
  $arr = $ms_.ToArray()
  $bw.Dispose(); $ms_.Dispose()
  return $arr
}

$udp = New-Object System.Net.Sockets.UdpClient
$udp.Client.Bind((New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, $ListenPort)))
$dst = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Parse("127.0.0.1"), $PluginPort)

$seq = 0
$angle = 0.0
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$lastRx = "(none)"
$rxCount = 0
$sentCount = 0
$tick = 0

while ($sw.Elapsed.TotalSeconds -lt $DurationSec) {
  $feet = GetPlayerFeet
  if ($feet -and ([Math]::Abs($feet.x) + [Math]::Abs($feet.y) -gt 100)) {
    $angle += 0.025
    $px = [single]($feet.x + [Math]::Cos($angle) * $Radius)
    $py = [single]($feet.y + [Math]::Sin($angle) * $Radius)
    $pz = [single]($feet.z)
    $qz = [single][Math]::Sin($angle / 2.0)
    $qw = [single][Math]::Cos($angle / 2.0)
    $ms = [uint32]($sw.Elapsed.TotalMilliseconds)
    $bytes = BuildPacket $seq $px $py $pz 0 0 $qz $qw $ms
    [void]$udp.Send($bytes, $bytes.Length, $dst)
    $seq++
    $sentCount++
    $tick++
    if ($tick % 20 -eq 0) {
      "  sent #{0,5} from ({1:F1},{2:F1},{3:F1})  player=({4:F1},{5:F1})  rx={6}" -f $seq, $px, $py, $pz, $feet.x, $feet.y, $rxCount
    }
  }
  if ($udp.Available -gt 0) {
    $remoteEP = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)
    $recv = $udp.Receive([ref]$remoteEP)
    $rxCount++
    if ($recv.Length -ge 28) {
      $rp = "({0:F1},{1:F1},{2:F1})" -f ([BitConverter]::ToSingle($recv,16)), ([BitConverter]::ToSingle($recv,20)), ([BitConverter]::ToSingle($recv,24))
      $lastRx = "len=$($recv.Length) from $($remoteEP.Address):$($remoteEP.Port) pos=$rp"
    } else {
      $lastRx = "len=$($recv.Length)"
    }
  }
  Start-Sleep -Milliseconds 50
}
"sent $sentCount packets; received $rxCount from the plugin"
"last plugin packet: $lastRx"
[void][FP]::CloseHandle($h)
$udp.Close()
"done"
