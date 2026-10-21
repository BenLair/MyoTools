param(
 [Parameter(Mandatory=$true)][string]$LauncherPath,
 [Parameter(Mandatory=$true)][string]$LegacyLauncherPath,
 [Parameter(Mandatory=$true)][string]$PreviousLauncherPath,
 [switch]$Remove
)
$ErrorActionPreference = "Stop"
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
if (-not $desktop) { throw "Desktop folder could not be found" }
$shortcut = Join-Path $desktop "MyoTools.lnk"
if (-not (Test-Path -LiteralPath $shortcut)) {
 Write-Output "MyoTools desktop shortcut is absent."
 exit 0
}
$item = Get-Item -LiteralPath $shortcut -Force
if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
 throw "Linked desktop shortcut is protected."
}
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$matchesInstallation = $false
foreach ($candidate in @($LauncherPath, $LegacyLauncherPath, $PreviousLauncherPath)) {
 $expectedArguments = '/k ""' + $candidate + '""'
 if (($link.Arguments -ceq $expectedArguments) -and
     ($link.WorkingDirectory -ieq (Split-Path -Parent $candidate))) {
  $matchesInstallation = $true
 }
}
if (($link.TargetPath -ine "$env:WINDIR\System32\cmd.exe") -or (-not $matchesInstallation)) {
 throw "MyoTools desktop shortcut targets another installation; retained."
}
if ($Remove) {
 Remove-Item -LiteralPath $shortcut
 Write-Output "Removed desktop shortcut: $shortcut"
} else {
 Write-Output "Desktop shortcut belongs to this installation: $shortcut"
}
