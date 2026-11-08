# 내가 띄운 Eden(PID 지정)만 캡처·입력한다.
#   eden_ctl.ps1 -EdenPid N -Shot out.png
#   eden_ctl.ps1 -EdenPid N -Keys "X,X,Down,X" [-HoldMs 120] [-GapMs 400]
param([int]$EdenPid, [string]$Shot, [string]$Keys, [int]$HoldMs = 120, [int]$GapMs = 450, [switch]$Post, [switch]$NoFocus)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint c, uint t);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc f, IntPtr l);
  public struct RECT { public int L, T, R, B; }
}
"@
[W]::SetProcessDPIAware() | Out-Null
$p = Get-Process -Id $EdenPid -ErrorAction Stop
$h = $p.MainWindowHandle
if ($h -eq [IntPtr]::Zero) { throw "창 없음" }
if (-not $NoFocus -and -not $Post) {
  [W]::ShowWindow($h, 9) | Out-Null
  [W]::BringWindowToTop($h) | Out-Null
  [W]::SetForegroundWindow($h) | Out-Null
  Start-Sleep -Milliseconds 250
}
$fg = [W]::GetForegroundWindow()
$targets = New-Object System.Collections.ArrayList
[void]$targets.Add($h)
[W]::EnumChildWindows($h, { param($c, $l) [void]$targets.Add($c); $true }, [IntPtr]::Zero) | Out-Null
$vk = @{ 'X'=0x58; 'Z'=0x5A; 'S'=0x53; 'A'=0x41; 'Q'=0x51; 'W'=0x57; 'C'=0x43; 'Enter'=0x0D;
         'Left'=0x25; 'Up'=0x26; 'Right'=0x27; 'Down'=0x28; 'Esc'=0x1B; 'F11'=0x7A; 'F4'=0x73 }
if ($Keys -and -not $Post -and $fg -ne $h) { throw "Eden 이 맨 앞 창이 아니라 입력하지 않음 (다른 창에 키가 갈 수 있음)" }
if ($Keys) {
  foreach ($k in $Keys.Split(',')) {
    $k = $k.Trim()
    if ($k -match '^wait(\d+)$') { Start-Sleep -Milliseconds ([int]$Matches[1]); continue }
    $code = [byte]$vk[$k]
    $ext = 0; if ($code -ge 0x25 -and $code -le 0x28) { $ext = 1 }
    if ($Post) {
      $sc = [W]::MapVirtualKey($code, 0)
      $ld = [IntPtr](1 -bor ($sc -shl 16) -bor ($ext -shl 24))
      $lu = [IntPtr]([int64](1 -bor ($sc -shl 16) -bor ($ext -shl 24)) -bor 0xC0000000L)
      foreach ($t in $targets) { [W]::PostMessage($t, 0x100, [IntPtr]$code, $ld) | Out-Null }
      Start-Sleep -Milliseconds $HoldMs
      foreach ($t in $targets) { [W]::PostMessage($t, 0x101, [IntPtr]$code, $lu) | Out-Null }
    } else {
      [W]::keybd_event($code, 0, $ext, [UIntPtr]::Zero)
      Start-Sleep -Milliseconds $HoldMs
      [W]::keybd_event($code, 0, 2 -bor $ext, [UIntPtr]::Zero)
    }
    Start-Sleep -Milliseconds $GapMs
  }
}
if ($Shot) {
  $r = New-Object W+RECT
  [W]::GetWindowRect($h, [ref]$r) | Out-Null
  $w = $r.R - $r.L; $hh = $r.B - $r.T
  $bmp = New-Object System.Drawing.Bitmap $w, $hh
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  [W]::PrintWindow($h, $hdc, 2) | Out-Null
  $g.ReleaseHdc($hdc)
  $bmp.Save($Shot, [System.Drawing.Imaging.ImageFormat]::Png)
  "shot $w x $hh fg=$($fg -eq $h)"
}
