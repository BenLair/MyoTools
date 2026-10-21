param(
 [Parameter(Mandatory=$true)][string]$LauncherPath,
 [Parameter(Mandatory=$true)][string]$IconPath
)
$ErrorActionPreference = "Stop"
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
if (-not $desktop) { throw "Desktop folder could not be found" }
$shortcut = Join-Path $desktop "MyoTools.lnk"
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = "$env:WINDIR\System32\cmd.exe"
$link.Arguments = '/k ""' + $LauncherPath + '""'
$link.WorkingDirectory = Split-Path -Parent $LauncherPath
$link.IconLocation = $IconPath + ",0"
$link.Description = "MyoTools - Muscle image analysis suite"
$link.Save()
Write-Host "Desktop shortcut created: $shortcut"
