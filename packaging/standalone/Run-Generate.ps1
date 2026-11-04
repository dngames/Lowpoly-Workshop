# Pixal3D standalone generation - no AI agent needed.
# Normal use: double-click Run-Generate.cmd (CPU) or Run-Generate-GPU.cmd (GPU).
# Manual: powershell -NoProfile -ExecutionPolicy Bypass -File Run-Generate.ps1 [-GpuIndex -1] [-Threads 4] [-PrepOnly]
param(
  [int]$GpuIndex = -1,   # -1 = CPU, 0 = first GPU (AMD Vulkan / NVIDIA CUDA)
  [int]$Threads = 0,     # 0 = auto (physical cores); CPU runs only
  [switch]$PrepOnly       # stop after input preparation (fast self-test, no weights needed)
)
$ErrorActionPreference = 'Stop'
$PackRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Seed = 42
$Budget = 1500
$Height = 2.4
$NodeName = 'Crate'

if ($Threads -le 0) {
  $Threads = [math]::Max(1, (Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum)
}

Start-Transcript -Path (Join-Path $PackRoot 'job\run.log') -Append -ErrorAction SilentlyContinue | Out-Null
try {
  Write-Output "=== Pixal3D standalone run (gpu=$GpuIndex threads=$Threads) ==="

  # 1. Python: bundled private interpreter first, system Python as fallback.
  $env:PYTHONNOUSERSITE = '1'
  $py = Join-Path $PackRoot 'python\python.exe'
  $launchArgsPrefix = @()
  if (-not (Test-Path $py)) {
    Write-Output 'Bundled Python missing, falling back to system Python ...'
    $syspy = $null
    if (Get-Command py -ErrorAction SilentlyContinue) { $syspy = 'py -3' }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $syspy = (Get-Command python -ErrorAction SilentlyContinue).Source }
    if (-not $syspy) { throw 'No Python found and no bundled interpreter. Re-extract the pack.' }
    $venvpy = Join-Path $PackRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvpy)) {
      Write-Output 'Creating .venv ...'
      Invoke-Expression "$syspy -m venv $($PackRoot + '\.venv')"
      Write-Output 'Installing wheels ...'
      & $venvpy -m pip install --no-index --find-links (Join-Path $PackRoot 'wheels') numpy scipy Pillow opencv-python-headless
    }
    $py = $venvpy
  }
  & $py -c "import sys; print('Python', sys.version.split()[0])"

  # 2. Environment: hermetic launcher, trellis-cli + weights discovery.
  $env:LOWPOLY_PIXAL3D_BIN = Join-Path $PackRoot 'runtime-vulkan\trellis-cli.exe'
  $env:LOWPOLY_PIXAL3D_MODELS_SV = Join-Path $PackRoot 'models-sv'
  $env:LOWPOLY_PIXAL3D_THREADS = "$Threads"
  $launch = Join-Path $PackRoot 'launch.py'

  # 3. Job folder (fresh copy of the smoke asset on first run).
  $job = Join-Path $PackRoot 'job'
  if (-not (Test-Path (Join-Path $job 'asset.json'))) {
    Write-Output 'Setting up job folder ...'
    New-Item -ItemType Directory -Force -Path $job | Out-Null
    Copy-Item (Join-Path $PackRoot 'smoke-asset\*') $job -Recurse -Force
  }
  function Run-Step($stepArgs, $label) {
    Write-Output "--- $label ---"
    & $py $launch @stepArgs
    if ($LASTEXITCODE -ne 0) { throw "$label failed (exit $LASTEXITCODE). See job\run.log." }
  }

  # 4. Prepare RGBA input (fast, no weights needed).
  Run-Step @($job, 'pixal3d', 'prep', '--mode', 'sv', '--size', '1024') 'prep'
  if ($PrepOnly) { Write-Output 'PREP-ONLY OK:'; Get-Item (Join-Path $job 'inputs\pixal3d\sv_input.png') | Select-Object FullName, Length; return }

  # 5. Generate (slow: minutes on GPU, hours/days on CPU - progress streams live).
  Run-Step @($job, 'pixal3d', 'run', '--mode', 'sv', '--gpu', "$GpuIndex", '--threads', "$Threads", '--atlas', '1024', '--seed', "$Seed") 'generate'
  Get-Item (Join-Path $job 'inputs\pixal3d_raw.glb') | Select-Object FullName, Length

  # 6. Blender stages (best effort - skipped cleanly when Blender is absent).
  $blender = $env:KIT_BLENDER
  if (-not $blender) { $blender = (Get-Command blender -ErrorAction SilentlyContinue).Source }
  if (-not $blender) {
    Write-Output 'Blender not found - stopping after generation (this is normal).'
    Write-Output 'To finish: install Blender, set KIT_BLENDER to blender.exe, then run:'
    Write-Output "  pixal3d decimate --budget $Budget --height $Height --node $NodeName"
    Write-Output '  build --force'
    Write-Output '  check'
    Write-Output 'See workshop\docs\pixal3d.md section 3-4. Raw mesh: job\inputs\pixal3d_raw.glb'
    return
  }
  $env:KIT_BLENDER = $blender
  Write-Output "Blender: $blender"
  Run-Step @($job, 'pixal3d', 'decimate', '--budget', "$Budget", '--height', "$Height", '--node', $NodeName) 'decimate'
  Run-Step @($job, 'build', '--force') 'build'
  Run-Step @($job, 'check') 'check'
  Write-Output 'ALL DONE. Deliverable: job\out\model.glb'
} finally {
  Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
}
