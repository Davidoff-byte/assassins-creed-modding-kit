param(
  [ValidateSet("host","guest")] [string]$Role = "host",
  [int]$DurationSec = 180,
  [int]$PluginPort = 27810,   # the port the plugin binds (its LocalPort)
  [int]$MyPort = 27811,       # the port this script binds (the plugin's RemotePort)
  [string]$Name = "faker",
  [uint32]$SessionId = 3735928559, # 0xDEADBEEF (hex literal would overflow to negative int)
  [int]$EventCount = 3,       # distinct Event packets to send when Role=host
  [string]$SendKill = "",     # "x,y,z,maxhp": send one crafted NpcCombat KILL event (kind 5)
  [int]$SendKillAfterSec = 8  # seconds after session established before sending it
)

# Coop session fake peer for AC4BFSP PatchFix v0.3 (C1 handshake + event channel).
#
#   host  -> the plugin is configured IsHost=false (guest): we answer its Hello with
#            Welcome, then send Player samples + Event packets (with one deliberate
#            duplicate) and verify the plugin's cum-ack shows up in its Player packets.
#   guest -> the plugin is configured IsHost=true: we send Hello until Welcome, then
#            send Player samples.
#
# Wire: Envelope 16B (magic 0x50524341, ver 1, type, seq, client_id)
#   Hello(4)  = proto_ver u16, reserved u16, save_fp u32, name[32]
#   Welcome(5)= session_id u32, host_id u32, save_fp u32, host_name[32]
#   Event(3)  = kind u16, data_len u16, event_id u32, data[40]
#   Player(1) = 56B payload; ack_seq lives at byte offset 68.

# --- game memory (to circle the ghost around the live player) ---
$gp = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
$pidG = if ($gp) { $gp.Id } else { 0 }
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class FP2 {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
$h = if ($pidG) { [FP2]::OpenProcess(0x0410, $false, $pidG) } else { [IntPtr]::Zero }
function GetMem2([int64]$a, [int]$n) { $b = New-Object byte[] $n; $r = [IntPtr]::Zero; [void][FP2]::ReadProcessMemory($h, [IntPtr]$a, $b, $n, [ref]$r); return $b }
function GetU322([int64]$a) { return [BitConverter]::ToUInt32((GetMem2 $a 4), 0) }
function GetPlayerFeet {
  if ($h -eq [IntPtr]::Zero) { return $null }
  $mgr = GetU322 0x2ABE588
  if ($mgr -eq 0) { return $null }
  $holder = GetU322 ($mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = GetU322 $holder; if ($camobj -eq 0) { return $null }
  $block = GetU322 ($camobj + 0x68); if ($block -eq 0) { return $null }
  $prov = GetU322 ($block + 0x174)
  if ($prov -ne 0) {
    $b = GetMem2 ($prov + 0x110) 12
    return [pscustomobject]@{ x = [BitConverter]::ToSingle($b,0); y = [BitConverter]::ToSingle($b,4); z = [BitConverter]::ToSingle($b,8) }
  }
  # interior/loading: provider is null - fall back to the camera manager ring (like the plugin)
  $cnt = GetU322 ($mgr + 0x130)
  $idx = $cnt % 5
  $b = GetMem2 ($mgr + 0x90 + $idx * 0x10) 12
  return [pscustomobject]@{ x = [BitConverter]::ToSingle($b,0); y = [BitConverter]::ToSingle($b,4); z = [BitConverter]::ToSingle($b,8) }
}
"game pid = $pidG (feet tracking $(if ($h -eq [IntPtr]::Zero) { 'OFF' } else { 'ON' }))"

$udp = New-Object System.Net.Sockets.UdpClient
$bound = $false
for ($i = 0; $i -lt 10 -and -not $bound; $i++) {
  try {
    $udp.Client.Bind((New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, $MyPort)))
    $bound = $true
  } catch {
    Start-Sleep -Milliseconds 700
  }
}
if (-not $bound) { "FATAL: could not bind udp/$MyPort (port held?)"; exit 1 }
$dst = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Parse("127.0.0.1"), $PluginPort)
"fake peer: role=$Role name='$Name' bind=$MyPort -> plugin $PluginPort (localhost)"
"           press Ctrl+C to stop; duration ${DurationSec}s"

$sw = [System.Diagnostics.Stopwatch]::StartNew()
[int]$rxHello=0; [int]$rxWelcome=0; [int]$rxPlayer=0; [int]$rxEvent=0
[uint32]$maxPluginEventId=0; [uint32]$maxSeenAck=0
$killSent = $false
$lastAnim = 0
[bool]$established = $false
[uint32]$seq=0; [uint32]$evId=0
[int]$dupSent=0
$lastHello = $sw.Elapsed.TotalMilliseconds - 1000
$lastSamp  = $sw.Elapsed.TotalMilliseconds - 1000
$lastEvent = $sw.Elapsed.TotalMilliseconds - 1000
$lastLog   = $sw.Elapsed.TotalMilliseconds
$px=10.0; $py=20.0; $pz=3.0; $angle=0.0; $tick50=0; $anim=0

function New-Env([uint16]$type, [uint32]$cid) {
  $ms = New-Object System.IO.MemoryStream
  $bw = New-Object System.IO.BinaryWriter($ms)
  $bw.Write([uint32]0x50524341); $bw.Write([uint16]1); $bw.Write([uint16]$type)
  $bw.Write([uint32]($script:seq++)); $bw.Write([uint32]$cid)
  $bw.Flush(); $a = $ms.ToArray(); $bw.Dispose(); $ms.Dispose(); return $a
}
function Send-Hello {
  $payload = New-Object System.IO.MemoryStream
  $bw = New-Object System.IO.BinaryWriter($payload)
  $bw.Write([uint16]1); $bw.Write([uint16]0); $bw.Write([uint32]0)
  $nb = [System.Text.Encoding]::ASCII.GetBytes($script:Name)
  $buf = New-Object byte[] 32; [Array]::Copy($nb, $buf, [Math]::Min($nb.Length, 31))
  $bw.Write($buf); $bw.Flush()
  $pb = $payload.ToArray(); $bw.Dispose(); $payload.Dispose()
  $env = New-Env 4 2
  [void]$udp.Send(($env + $pb), ($env.Length + $pb.Length), $dst)
}
function Send-Welcome {
  $payload = New-Object System.IO.MemoryStream
  $bw = New-Object System.IO.BinaryWriter($payload)
  $bw.Write([uint32]$script:SessionId); $bw.Write([uint32]99); $bw.Write([uint32]0)
  $nb = [System.Text.Encoding]::ASCII.GetBytes($script:Name)
  $buf = New-Object byte[] 32; [Array]::Copy($nb, $buf, [Math]::Min($nb.Length, 31))
  $bw.Write($buf); $bw.Flush()
  $pb = $payload.ToArray(); $bw.Dispose(); $payload.Dispose()
  $env = New-Env 5 2
  [void]$udp.Send(($env + $pb), ($env.Length + $pb.Length), $dst)
  "  -> Welcome sent (session 0x{0:X8})" -f $script:SessionId
}
function Send-Player([uint32]$ack, [single]$px, [single]$py, [single]$pz, [uint32]$anim, [single]$qz, [single]$qw) {
  $ms = New-Object System.IO.MemoryStream
  $bw = New-Object System.IO.BinaryWriter($ms)
  <# payload #>
  $bw.Write([single]$px); $bw.Write([single]$py); $bw.Write([single]$pz)
  $bw.Write([single]0); $bw.Write([single]0); $bw.Write([single]$qz); $bw.Write([single]$qw)
  $bw.Write([single]0); $bw.Write([single]0); $bw.Write([single]0); $bw.Write([single]100)
  $bw.Write([uint32]$anim)      # anim_state (phase<<16 | flags<<8 | hang)
  $bw.Write([uint32]($sw.Elapsed.TotalMilliseconds))
  $bw.Write([uint32]$ack)       # ack_seq
  $bw.Flush(); $pb = $ms.ToArray(); $bw.Dispose(); $ms.Dispose()
  $env = New-Env 1 2
  [void]$udp.Send(($env + $pb), ($env.Length + $pb.Length), $dst)
}
function Send-Event([uint16]$kind, [uint32]$id, [byte[]]$data = $null) {
  $ms = New-Object System.IO.MemoryStream
  $bw = New-Object System.IO.BinaryWriter($ms)
  $dl = 0; if ($data) { $dl = $data.Length }
  $bw.Write([uint16]$kind); $bw.Write([uint16]$dl); $bw.Write([uint32]$id)
  if ($dl -gt 0) { $bw.Write($data) }
  $pad = New-Object byte[] (40 - $dl); $bw.Write($pad)
  $bw.Flush(); $pb = $ms.ToArray(); $bw.Dispose(); $ms.Dispose()
  $env = New-Env 3 2
  [void]$udp.Send(($env + $pb), ($env.Length + $pb.Length), $dst)
  "  -> Event id=$id kind=$kind len=$dl sent"
}

while ($sw.Elapsed.TotalSeconds -lt $DurationSec) {
  $now = $sw.Elapsed.TotalMilliseconds

  # receive
  if ($udp.Available -gt 0) {
    $remoteEP = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)
    try {
      $pkt = $udp.Receive([ref]$remoteEP)
    } catch [System.Net.Sockets.SocketException] {
      $pkt = $null # stale ICMP unreachable surfaces as WSAECONNRESET - ignore
    }
    if ($pkt -and $pkt.Length -ge 16) {
      $type = [BitConverter]::ToUInt16($pkt, 6)
      switch ($type) {
        1 { $rxPlayer++
            if ($pkt.Length -ge 72) {
              $ack = [BitConverter]::ToUInt32($pkt, 68)
              if ($ack -gt $maxSeenAck) { $maxSeenAck = $ack }
              # live player anim state (blend<<24|phase<<16|flags<<8|hang) -> echo back as ours,
              # so the plugin's ghost mirrors the player in solo parkour tests
              $lastAnim = [BitConverter]::ToUInt32($pkt, 60)
            } }
        3 { $rxEvent++
            $eid = [BitConverter]::ToUInt32($pkt, 20)
            $ekind = [BitConverter]::ToUInt16($pkt, 16)
            $edlen = [BitConverter]::ToUInt16($pkt, 18)
            if ($eid -gt $maxPluginEventId) { $maxPluginEventId = $eid }
            if ($ekind -eq 5 -and $pkt.Length -ge 48) {
              $px = [BitConverter]::ToSingle($pkt, 24); $py = [BitConverter]::ToSingle($pkt, 28); $pz = [BitConverter]::ToSingle($pkt, 32)
              $lb = [BitConverter]::ToUInt16($pkt, 36); $la = [BitConverter]::ToUInt16($pkt, 38)
              $mh = [BitConverter]::ToUInt16($pkt, 40); $eh = $pkt[42]
              "  <- NpcCombat id=$eid ev=$eh pos=({0:F1},{1:F1},{2:F1}) life $lb->$la max=$mh" -f $px, $py, $pz
            } else {
              "  <- Event id=$eid kind=$ekind len=$edlen"
            } }
        4 { $rxHello++
            $nm = [System.Text.Encoding]::ASCII.GetString($pkt, 24, 32).TrimEnd([char]0)
            "  <- Hello from plugin name='$nm' (client {0})" -f ([BitConverter]::ToUInt32($pkt,12))
            if ($Role -eq "host" -and -not $established) {
              $established = $true
              Send-Welcome
            } }
        5 { $rxWelcome++
            if (-not $established) {
              $established = $true
              $sid = [BitConverter]::ToUInt32($pkt, 16)
              $nm = [System.Text.Encoding]::ASCII.GetString($pkt, 28, 32).TrimEnd([char]0)
              "  <- Welcome from plugin session 0x{0:X8} host='{1}'" -f $sid, $nm
            } }
      }
    }
  }

  # guest: Hello every 500 ms until established
  if ($Role -eq "guest" -and -not $established -and ($now - $lastHello) -ge 500) {
    Send-Hello; $lastHello = $now
  }

  # once plugin packets are seen (or handshake completed): Player samples at 20 Hz -
  # circle the live player when readable. (Samples also carry the event ack.)
  if (($established -or $rxPlayer -gt 0) -and ($now - $lastSamp) -ge 50) {
    $feet = GetPlayerFeet
    if ($feet -and ([Math]::Abs($feet.x) + [Math]::Abs($feet.y) -gt 20 -or $feet.z -lt -1)) {
      $tick50++
      $px = [single]($feet.x + 1.6)
      $py = [single]($feet.y)
      $pz = [single]$feet.z
      $phase = [int](($tick50 / 40) % 4)
      $hang  = [int](($tick50 / 200) % 2)
      $fl    = [int](($tick50 / 100) % 2)
      $anim  = [uint32](([uint32]$phase -shl 16) -bor ([uint32]$fl -shl 8) -bor [uint32]$hang)
      if ($lastAnim -gt 0) { $anim = $lastAnim } # parkour mirror: echo the live player state
      $qz    = [single][Math]::Sin($angle / 2.0)
      $qw    = [single][Math]::Cos($angle / 2.0)
      Send-Player $maxPluginEventId $px $py $pz $anim $qz $qw
      if ($tick50 % 40 -eq 0) {
        "  -> player=({0:F1},{1:F1}) ghost=({2:F1},{3:F1},{4:F1}) anim=0x{5:X} phase={6} hang={7} fl={8}" -f `
          $feet.x, $feet.y, $px, $py, $pz, $anim, $phase, $hang, $fl
      }
    }
    $lastSamp = $now
  }

  # host: emit events (id 1..N, then re-send id 1 once -> dedupe test)
  if ($Role -eq "host" -and $established) {
    if ($evId -lt $EventCount -and ($now - $lastEvent) -ge 2000) {
      $evId++
      Send-Event 4 $evId
      $lastEvent = $now
    } elseif ($evId -eq $EventCount -and $dupSent -lt 1 -and ($now - $lastEvent) -ge 2000) {
      $dupSent++
      Send-Event 4 1
      "  (deliberate duplicate of id=1 - the plugin must log it only once)"
      $lastEvent = $now
    }
  }

  # optional one-shot crafted NPC kill (kind 5) for the RX test
  if ($SendKill -ne "" -and ($established -or $rxPlayer -gt 0) -and -not $killSent -and ($now / 1000) -ge $SendKillAfterSec) {
    $killSent = $true
    $parts = $SendKill.Split(",")
    $ms = New-Object System.IO.MemoryStream
    $bw = New-Object System.IO.BinaryWriter($ms)
    $bw.Write([single][double]$parts[0]); $bw.Write([single][double]$parts[1]); $bw.Write([single][double]$parts[2])
    $bw.Write([uint16]0); $bw.Write([uint16]65535); $bw.Write([uint16][int]$parts[3])
    $bw.Write([byte]1); $bw.Write([byte]0)
    $bw.Flush(); $kdata = $ms.ToArray(); $bw.Dispose(); $ms.Dispose()
    Send-Event 5 100 $kdata
    "  -> NpcCombat KILL sent at ($($parts[0]),$($parts[1]),$($parts[2])) maxhp=$($parts[3])"
  }

  if (($now - $lastLog) -ge 10000) {
    $lastLog = $now
    "  t={0:N0}s est={1} rx(player={2} hello={3} welcome={4} event={5}) maxPluginEvId={6} maxAckSeen={7}" -f `
      ($now/1000), $established, $rxPlayer, $rxHello, $rxWelcome, $rxEvent, $maxPluginEventId, $maxSeenAck
  }
  Start-Sleep -Milliseconds 15
}

"== summary =="
"established: $established  rxPlayer=$rxPlayer rxHello=$rxHello rxWelcome=$rxWelcome rxEvent=$rxEvent"
"max plugin event id = $maxPluginEventId ; max ack seen from plugin = $maxSeenAck"
if ($Role -eq "host") {
  if ($maxSeenAck -ge 1) { "ACK PATH OK - the peer cum-acked our events" } else { "NO ACK - the peer never acked our events" }
}
[void]$udp.Close()
"done"
