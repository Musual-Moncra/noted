# Noted Installer for Windows
# Usage: irm https://raw.githubusercontent.com/Musual-Moncra/noted/main/install.ps1 | iex

[CmdletBinding()]
param(
    [string]$Version = "latest",
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

$repo = "Musual-Moncra/noted"
$assetName = "noted-windows-x64.zip"

Write-Host "==> Installing Noted for Windows (x64)..." -ForegroundColor Cyan

# 1. Architecture Check
if (-not [System.Environment]::Is64BitOperatingSystem) {
    Write-Error "Only 64-bit Windows is supported."
    exit 1
}

# 2. Determine Install Directory
if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    if ($env:LOCALAPPDATA) {
        $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\noted"
    } else {
        $InstallDir = Join-Path $env:USERPROFILE ".local\bin"
    }
}

if (-not (Test-Path -Path $InstallDir)) {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
}

# 3. Resolve Download URL
if ($Version -eq "latest") {
    $downloadUrl = "https://github.com/$repo/releases/latest/download/$assetName"
} else {
    $downloadUrl = "https://github.com/$repo/releases/download/$Version/$assetName"
}

Write-Host "==> Downloading $assetName from GitHub Releases..." -ForegroundColor Cyan

# 4. Download and Extract via Temporary Directory
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("noted-install-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

try {
    $zipPath = Join-Path $tempDir $assetName

    # Ensure TLS 1.2+
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12

    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing

    Write-Host "==> Extracting files..." -ForegroundColor Cyan
    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force

    $notedExe = Get-ChildItem -Path $tempDir -Filter "noted.exe" -Recurse | Select-Object -First 1
    if (-not $notedExe) {
        Write-Error "Could not find noted.exe in downloaded archive."
        exit 1
    }

    $destNoted = Join-Path $InstallDir "noted.exe"
    $destNote = Join-Path $InstallDir "note.exe"

    Copy-Item -Path $notedExe.FullName -Destination $destNoted -Force
    Copy-Item -Path $notedExe.FullName -Destination $destNote -Force

    Write-Host "✓ Installed executable to $destNoted" -ForegroundColor Green
    Write-Host "✓ Created alias executable $destNote" -ForegroundColor Green

    # 5. Add to User PATH Environment Variable
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $pathParts = if ($userPath) { $userPath -split ';' } else { @() }

    $alreadyInPath = $false
    foreach ($p in $pathParts) {
        if ($p.TrimEnd('\') -eq $InstallDir.TrimEnd('\')) {
            $alreadyInPath = $true
            break
        }
    }

    if (-not $alreadyInPath) {
        $newPath = if ([string]::IsNullOrEmpty($userPath)) {
            $InstallDir
        } else {
            "$userPath;$InstallDir"
        }
        [System.Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Host "✓ Added $InstallDir to User PATH." -ForegroundColor Green
    }

    # Broadcast environment change to Windows explorer and new shells
    try {
        Add-Type -Namespace Win32 -Name NativeMethods -MemberDefinition @"
            [System.Runtime.InteropServices.DllImport("user32.dll", SetLastError = true, CharSet = System.Runtime.InteropServices.CharSet.Auto)]
            public static extern IntPtr SendMessageTimeout(
                IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam,
                uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
"@
        $result = [UIntPtr]::Zero
        [Win32.NativeMethods]::SendMessageTimeout([IntPtr]0xffff, 0x001A, [UIntPtr]::Zero, "Environment", 2, 3000, [ref]$result) | Out-Null
    } catch {
        # Non-fatal if broadcast fails
    }

    # Update current session PATH immediately
    $env:Path = "$InstallDir;$env:Path"

    Write-Host ""
    Write-Host "✨ Noted installed successfully!" -ForegroundColor Green
    Write-Host "👉 Bạn có thể gõ ngay " -NoNewline
    Write-Host "noted" -ForegroundColor Cyan -NoNewline
    Write-Host " hoặc " -NoNewline
    Write-Host "note" -ForegroundColor Cyan -NoNewline
    Write-Host " trong cửa sổ này để bắt đầu."
    Write-Host "⚠️  LƯU Ý: Với các cửa sổ Terminal/CMD đã mở từ TRƯỚC khi cài, hãy TẮT ĐI MỞ LẠI (hoặc mở Tab mới) để Windows cập nhật lệnh." -ForegroundColor Yellow
    Write-Host "💡 Mẹo: Hãy dùng Windows Terminal (wt.exe) kết hợp font Cascadia Code hoặc Nerd Font để giao diện hiển thị 24-bit TrueColor và Icon đẹp như macOS." -ForegroundColor Cyan
    Write-Host ""
}
finally {
    if (Test-Path -Path $tempDir) {
        Remove-Item -Recurse -Force -Path $tempDir -ErrorAction SilentlyContinue
    }
}
