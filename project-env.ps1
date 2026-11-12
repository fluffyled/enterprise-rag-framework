# Dot-source before installing packages or running project tools.
param([switch]$PersistCaches)
$cacheRoot = Join-Path $PSScriptRoot '.cache'
if ([System.IO.Path]::GetPathRoot($cacheRoot) -ne 'D:\') { throw 'Project storage must stay on drive D:' }
$cachePaths = @{
    PIP_CACHE_DIR = 'pip'
    HF_HOME = 'huggingface'
    HF_HUB_CACHE = 'huggingface/hub'
    HF_ASSETS_CACHE = 'huggingface/assets'
    HF_DATASETS_CACHE = 'huggingface/datasets'
    TORCH_HOME = 'torch'
    SENTENCE_TRANSFORMERS_HOME = 'sentence-transformers'
    XDG_CACHE_HOME = 'xdg'
}
foreach ($entry in $cachePaths.GetEnumerator()) {
    $cachePath = Join-Path $cacheRoot $entry.Value
    New-Item -ItemType Directory -Path $cachePath -Force | Out-Null
    [Environment]::SetEnvironmentVariable($entry.Key, $cachePath, 'Process')
    if ($PersistCaches) { [Environment]::SetEnvironmentVariable($entry.Key, $cachePath, 'User') }
}
$tempPath = Join-Path $cacheRoot 'tmp'
New-Item -ItemType Directory -Path $tempPath -Force | Out-Null
foreach ($key in @('TEMP', 'TMP', 'TMPDIR')) { [Environment]::SetEnvironmentVariable($key, $tempPath, 'Process') }
$env:PYTHONDONTWRITEBYTECODE = '1'

# CUDA tools and compiler caches stay inside the project on D:.
$env:CUDA_PATH = Join-Path $PSScriptRoot 'tools\cuda\v12.6'
$env:CUDA_HOME = $env:CUDA_PATH
$cudaBin = Join-Path $env:CUDA_PATH 'bin'
if ((Test-Path -LiteralPath $cudaBin) -and ($env:PATH -split ';' -notcontains $cudaBin)) { $env:PATH = "$cudaBin;$env:PATH" }
$env:CUDA_CACHE_PATH = Join-Path $cacheRoot 'cuda'
$env:TORCH_EXTENSIONS_DIR = Join-Path $cacheRoot 'torch-extensions'
$env:TRITON_CACHE_DIR = Join-Path $cacheRoot 'triton'
