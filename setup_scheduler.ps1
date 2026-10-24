# ============================================================
# setup_scheduler.ps1
# ينشئ مهمة مجدولة في Windows Task Scheduler لرفع فيديوهات
# Shorts يومياً بشكل تلقائي.
# يجب تشغيله كمسؤول (Run as Administrator).
# ============================================================

$ErrorActionPreference = "Stop"

$TaskName = "YouTube Shorts Daily Upload"
$ProjectDir = "c:\Users\Lenovo\Desktop\يوتيوب short"
$PythonExe = (Get-Command python).Source
$ScriptPath = Join-Path $ProjectDir "upload_shorts.py"

Write-Host "Creating scheduled task: $TaskName"
Write-Host "  Python   : $PythonExe"
Write-Host "  Script   : $ScriptPath"
Write-Host "  Working  : $ProjectDir"

# حذف مهمة سابقة إن وُجدت لتجنب التعارض
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Deleting previous task to update it..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

$action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$ScriptPath`" --privacy public" `
    -WorkingDirectory $ProjectDir

$trigger = New-ScheduledTaskTrigger -Daily -At "10:00"

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "رفع يومي تلقائي لفيديوهات Shorts إلى يوتيوب عبر YouTube Data API v3." `
    -Force

Write-Host ""
Write-Host "Task registered successfully."
Write-Host "  - View it: taskschd.msc  ->  Task Scheduler Library"
Write-Host "  - Run it now manually:"
Write-Host "    schtasks /run /tn `"$TaskName`""
Write-Host "  - Delete it:"
Write-Host "    schtasks /delete /tn `"$TaskName`" /f"
