$ErrorActionPreference = "Stop"
$ProgressPreference = 'SilentlyContinue'
$Candidates = @(
  $env:MYOTOOLS_CONDA_EXE,
  (Join-Path $env:USERPROFILE "miniforge3\Scripts\conda.exe"),
  (Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe"),
  (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe")
)
$runtimePath = Join-Path $PSScriptRoot "..\..\runtime\conda_path.txt"
if (Test-Path $runtimePath) { $Candidates = @((Get-Content $runtimePath -Raw).Trim()) + $Candidates }
try {
  $inPath = (Get-Command conda.exe -ErrorAction SilentlyContinue).Source
  if ($inPath) { $Candidates += $inPath }
} catch {}
$Conda = $null
foreach ($candidate in $Candidates) {
  if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { $Conda = $candidate; break }
}
if (-not $Conda) {
  $version = "26.7.2-0"
  $file = "Miniforge3-$version-Windows-x86_64.exe"
  $url = "https://github.com/conda-forge/miniforge/releases/download/$version/$file"
  $expected = "71cf9519087be74fa53021219ff292beb2fc05fa49e0bb6eb0e0b6b14fccbaab"
  $target = Join-Path $env:USERPROFILE "miniforge3"
  if (Test-Path $target) { throw "Existing incomplete Miniforge directory: $target. Resolve it before installing." }
  $tempInstaller = Join-Path $env:TEMP $file
  Write-Host "Downloading verified Miniforge installer..."
  try {
    Invoke-WebRequest -Uri $url -OutFile $tempInstaller -UseBasicParsing
    $actual = (Get-FileHash -LiteralPath $tempInstaller -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "Miniforge SHA-256 mismatch. Installation aborted." }
    Write-Host "Installing Miniforge silently for the current user..."
    $process = Start-Process -FilePath $tempInstaller -ArgumentList @('/InstallationType=JustMe','/RegisterPython=0','/AddToPath=0','/S',("/D=$target")) -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Miniforge installer exited with $($process.ExitCode)" }
  } finally { Remove-Item -LiteralPath $tempInstaller -Force -ErrorAction SilentlyContinue }
  $Conda = Join-Path $target "Scripts\conda.exe"
}
if (!(Test-Path -LiteralPath $Conda -PathType Leaf)) { throw "Conda executable not found: $Conda" }
$base = (& $Conda info --base).Trim()
if ($LASTEXITCODE -ne 0) { throw "Could not determine Conda base directory" }
$Python = Join-Path $base "python.exe"
if (!(Test-Path $Python)) { throw "Conda base Python not found: $Python" }
& $Python (Join-Path $PSScriptRoot "..\..\setup_environment.py") --conda $Conda --platform windows
if ($LASTEXITCODE -ne 0) { throw "MyoTools environment setup failed." }
