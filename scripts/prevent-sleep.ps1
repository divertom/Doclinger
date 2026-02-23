# Keep the PC awake while this script is running (e.g. during long Docling extractions).
# Press Ctrl+C to stop; sleep settings then return to normal.
# Requires PowerShell 5+ (Windows).

$code = @"
using System;
using System.Runtime.InteropServices;
public class SleepBlock {
    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
    public const uint ES_CONTINUOUS     = 0x80000000;
    public const uint ES_SYSTEM_REQUIRED = 0x00000001;
    public const uint ES_DISPLAY_REQUIRED = 0x00000002;
}
"@
Add-Type -TypeDefinition $code -ErrorAction SilentlyContinue | Out-Null

$flags = [SleepBlock]::ES_CONTINUOUS -bor [SleepBlock]::ES_SYSTEM_REQUIRED -bor [SleepBlock]::ES_DISPLAY_REQUIRED
[SleepBlock]::SetThreadExecutionState($flags) | Out-Null

Write-Host "PC will stay awake while this window is open. Press Ctrl+C when extraction is done."
try {
    while ($true) { Start-Sleep -Seconds 60 }
} finally {
    [SleepBlock]::SetThreadExecutionState([SleepBlock]::ES_CONTINUOUS) | Out-Null
    Write-Host "Stopped. Normal sleep behavior resumed."
}
