[CmdletBinding()]
param(
    [string]$InstallRoot = "C:\hec\python\pythonCWMS",
    [switch]$Force,

    # These two inputs are used only by the repository's isolated fixture tests.
    [Parameter(DontShow = $true)]
    [string]$ConfigFile,
    [Parameter(DontShow = $true)]
    [string]$PublicKeyFile
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ConfigUrl = "https://github.com/USACE-WaterManagement/pythonCWMS/releases/latest/download/pythonCWMS_config.json"
$ReleasePublicKeyPem = @'
-----BEGIN PUBLIC KEY-----
MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAzklEzbXZIq3nCn9r/KMF
O/0oPb4fNkmiCPurHJoC7yorxxSORhl6o/Mmh9hNTrqg+fgS/bKds9nlIEnFOhVG
G2hSHm3UsbQPN9RovDqT5fUSI+qRULffWtGM6JKdcQ6vADUaMj+h9U6xJiBDEEvg
kAlr4XVJucwx0fkxTc0gfLWjVGzbZ1UeNLcAO3i6vgHML1HyFGNbbzWmKiDYmux6
fDJnbBHx0EzfkWksZBd+i9VSwpLYs7+aXKQp31RD0xrSky89JMTwoWvCe0RdjunS
PfFlGgF/u50iolCzvf8A27VBCTAK43AQ7MBrHhqwjpRNUKHbik+AVppNiO4dNrdw
t63yMmeoX96uv2OjRgkN+DHBR+CKh+3+usqqAtCM4bvmXVBdy2YMblnlAS1MWGu3
O8tLhAKWsj+S3DMCOOQwLnO1LP0B8qeootWor4+1QOMf3u1anL8Id3DmF58PbUma
lnhhYtfCPLW1LlMaA68Tdzil4R5uqpmwghQ0e3k6x9fJAgMBAAE=
-----END PUBLIC KEY-----
'@

function Get-HttpsFile {
    param([string]$Source, [string]$Destination, [bool]$AllowLocal)

    if ($AllowLocal -and [System.IO.File]::Exists($Source)) {
        [System.IO.File]::Copy($Source, $Destination, $false)
        return
    }

    $uri = $null
    if (-not [System.Uri]::TryCreate($Source, [System.UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -ne [System.Uri]::UriSchemeHttps) {
        throw "Download URL must be an absolute HTTPS URL: $Source"
    }
    # Windows PowerShell 5.1's progress rendering can make large downloads
    # dramatically slower. Suppressing it does not change TLS validation.
    $previousProgressPreference = $ProgressPreference
    try {
        $ProgressPreference = "SilentlyContinue"
        Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile $Destination
    }
    finally {
        $ProgressPreference = $previousProgressPreference
    }
}

function Assert-DownloadSource {
    param([string]$Source, [string]$Name, [bool]$AllowLocal)

    if ([string]::IsNullOrWhiteSpace($Source)) {
        throw "Configuration field '$Name' must not be empty."
    }
    if ($AllowLocal -and [System.IO.Path]::IsPathRooted($Source)) { return }

    $uri = $null
    if (-not [System.Uri]::TryCreate($Source, [System.UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -ne [System.Uri]::UriSchemeHttps) {
        throw "Configuration field '$Name' must contain an absolute HTTPS URL."
    }
}

function Read-DerLength {
    param([byte[]]$Bytes, [ref]$Offset)

    if ($Offset.Value -ge $Bytes.Length) { throw "Invalid public key DER length." }
    $first = [int]$Bytes[$Offset.Value]
    $Offset.Value++
    if (($first -band 0x80) -eq 0) { return $first }

    $count = $first -band 0x7f
    if ($count -lt 1 -or $count -gt 4 -or $Offset.Value + $count -gt $Bytes.Length) {
        throw "Invalid public key DER length."
    }
    $length = 0
    for ($i = 0; $i -lt $count; $i++) {
        $length = ($length -shl 8) -bor [int]$Bytes[$Offset.Value]
        $Offset.Value++
    }
    return $length
}

function Read-DerValue {
    param([byte[]]$Bytes, [ref]$Offset, [int]$ExpectedTag)

    if ($Offset.Value -ge $Bytes.Length -or [int]$Bytes[$Offset.Value] -ne $ExpectedTag) {
        throw "Unexpected public key DER structure."
    }
    $Offset.Value++
    $length = Read-DerLength $Bytes $Offset
    if ($length -lt 0 -or $Offset.Value + $length -gt $Bytes.Length) {
        throw "Invalid public key DER value."
    }
    $value = New-Object byte[] $length
    [System.Array]::Copy($Bytes, $Offset.Value, $value, 0, $length)
    $Offset.Value += $length
    return $value
}

function Remove-LeadingZero {
    param([byte[]]$Value)
    if ($Value.Length -gt 1 -and $Value[0] -eq 0) {
        $trimmed = New-Object byte[] ($Value.Length - 1)
        [System.Array]::Copy($Value, 1, $trimmed, 0, $trimmed.Length)
        return $trimmed
    }
    return $Value
}

function New-RsaFromPublicKeyPem {
    param([string]$Pem)

    $base64 = $Pem -replace '-----BEGIN PUBLIC KEY-----', '' -replace '-----END PUBLIC KEY-----', '' -replace '\s', ''
    $der = [System.Convert]::FromBase64String($base64)
    $offset = 0
    $spki = Read-DerValue $der ([ref]$offset) 0x30
    $spkiOffset = 0
    $null = Read-DerValue $spki ([ref]$spkiOffset) 0x30
    $bitString = Read-DerValue $spki ([ref]$spkiOffset) 0x03
    if ($bitString.Length -lt 2 -or $bitString[0] -ne 0) { throw "Invalid RSA public key bit string." }

    $rsaDer = New-Object byte[] ($bitString.Length - 1)
    [System.Array]::Copy($bitString, 1, $rsaDer, 0, $rsaDer.Length)
    $rsaOffset = 0
    $rsaSequence = Read-DerValue $rsaDer ([ref]$rsaOffset) 0x30
    $sequenceOffset = 0
    $modulus = Remove-LeadingZero (Read-DerValue $rsaSequence ([ref]$sequenceOffset) 0x02)
    $exponent = Remove-LeadingZero (Read-DerValue $rsaSequence ([ref]$sequenceOffset) 0x02)

    $parameters = New-Object System.Security.Cryptography.RSAParameters
    $parameters.Modulus = $modulus
    $parameters.Exponent = $exponent
    $rsa = New-Object System.Security.Cryptography.RSACryptoServiceProvider
    $rsa.PersistKeyInCsp = $false
    $rsa.ImportParameters($parameters)
    return $rsa
}

function Convert-HexToBytes {
    param([string]$Hex)
    $bytes = New-Object byte[] ($Hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [System.Convert]::ToByte($Hex.Substring($i * 2, 2), 16)
    }
    return $bytes
}

function Test-ArchiveSignature {
    param([string]$ArchivePath, [string]$SignaturePath, [string]$PublicKeyPem, [string]$HashHex)

    $rsa = New-RsaFromPublicKeyPem $PublicKeyPem
    try {
        $signature = [System.IO.File]::ReadAllBytes($SignaturePath)
        $hash = Convert-HexToBytes $HashHex
        $oid = [System.Security.Cryptography.CryptoConfig]::MapNameToOID("SHA256")
        try { return $rsa.VerifyHash($hash, $oid, $signature) }
        catch [System.Security.Cryptography.CryptographicException] { return $false }
    }
    finally {
        $rsa.Dispose()
    }
}

function Expand-SafeZip {
    param([string]$ArchivePath, [string]$Destination)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $destinationFull = [System.IO.Path]::GetFullPath($Destination)
    $destinationPrefix = $destinationFull.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    $zip = [System.IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.Replace('\', '/')
            $segments = $name.Split('/')
            $unixType = ($entry.ExternalAttributes -shr 16) -band 0xf000
            $windowsAttributes = $entry.ExternalAttributes -band 0xffff

            if ([string]::IsNullOrWhiteSpace($name) -or $name.StartsWith('/') -or
                [System.IO.Path]::IsPathRooted($name) -or $name.Contains(':') -or
                ($segments -contains '..') -or $unixType -eq 0xa000 -or
                ($windowsAttributes -band [int][System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Unsafe ZIP entry rejected: $($entry.FullName)"
            }

            $relative = $name.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
            $outputPath = [System.IO.Path]::GetFullPath((Join-Path $destinationFull $relative))
            if (-not $outputPath.StartsWith($destinationPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "ZIP entry escapes the staging directory: $($entry.FullName)"
            }

            if ($name.EndsWith('/')) {
                [System.IO.Directory]::CreateDirectory($outputPath) | Out-Null
                continue
            }

            $parent = [System.IO.Path]::GetDirectoryName($outputPath)
            [System.IO.Directory]::CreateDirectory($parent) | Out-Null
            $inputStream = $entry.Open()
            $outputStream = $null
            try {
                $outputStream = [System.IO.File]::Open($outputPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
                $inputStream.CopyTo($outputStream)
            }
            finally {
                if ($null -ne $outputStream) { $outputStream.Dispose() }
                $inputStream.Dispose()
            }
        }
    }
    finally {
        $zip.Dispose()
    }
}

function Send-EnvironmentChanged {
    try {
        if (-not ('PythonCwmsEnvironmentBroadcast' -as [type])) {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class PythonCwmsEnvironmentBroadcast {
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr SendMessageTimeout(
        IntPtr hWnd, uint message, UIntPtr wParam, string lParam,
        uint flags, uint timeout, out UIntPtr result);
}
'@
        }

        $result = [UIntPtr]::Zero
        [void][PythonCwmsEnvironmentBroadcast]::SendMessageTimeout(
            [IntPtr]0xffff, 0x001a, [UIntPtr]::Zero, 'Environment', 0x0002, 5000, [ref]$result)
    }
    catch {
        Write-Warning "Could not notify running applications about the environment change. Close all terminal windows or sign out before using Python CWMS."
    }
}

function Set-UserEnvironment {
    param([string]$PythonHome, [string]$PreviousPythonHome)

    $environmentKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Environment')
    try {
        $pathValue = $environmentKey.GetValue(
            'Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $parts = New-Object System.Collections.Generic.List[string]
        if (-not [string]::IsNullOrWhiteSpace([string]$pathValue)) {
            foreach ($part in ([string]$pathValue).Split(';')) {
                if ([string]::IsNullOrWhiteSpace($part)) { continue }
                $normalized = $part.Trim().Trim('"').TrimEnd([char[]]'\/')
                $isManagedEntry = (
                    $normalized -ieq '%PYTHON_CWMS_HOME%' -or
                    $normalized -ieq '%PYTHON_CWMS_HOME%\Scripts' -or
                    $normalized -ieq $PythonHome.TrimEnd([char[]]'\/') -or
                    $normalized -ieq (Join-Path $PythonHome 'Scripts').TrimEnd([char[]]'\/') -or
                    (-not [string]::IsNullOrWhiteSpace($PreviousPythonHome) -and
                        ($normalized -ieq $PreviousPythonHome.TrimEnd([char[]]'\/') -or
                         $normalized -ieq (Join-Path $PreviousPythonHome 'Scripts').TrimEnd([char[]]'\/'))) -or
                    $normalized -match '(?i)[\\/]pythonCWMS[\\/]python(?:[\\/]Scripts)?$'
                )
                if (-not $isManagedEntry) { $parts.Add($part.Trim()) }
            }
        }

        # Keep the managed interpreter ahead of WindowsApps and other user-level
        # Python installations while preserving all unrelated PATH entries.
        $parts.Insert(0, '%PYTHON_CWMS_HOME%\Scripts')
        $parts.Insert(0, '%PYTHON_CWMS_HOME%')
        $environmentKey.SetValue(
            'PYTHON_CWMS_HOME', $PythonHome, [Microsoft.Win32.RegistryValueKind]::String)
        $environmentKey.SetValue(
            'Path', ($parts -join ';'), [Microsoft.Win32.RegistryValueKind]::ExpandString)
    }
    finally {
        $environmentKey.Dispose()
    }

    Send-EnvironmentChanged
}

$workRoot = $null
$backupPath = $null
$installedTargetCreated = $false
$environmentStarted = $false
$oldHome = $null
$oldPath = $null
$exitCode = 1

try {
    if ([string]::IsNullOrWhiteSpace($InstallRoot)) { throw "InstallRoot must not be empty." }
    $InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
    $trimmedRoot = $InstallRoot.TrimEnd([char[]]'\/')
    if ([string]::IsNullOrWhiteSpace([System.IO.Path]::GetFileName($trimmedRoot))) {
        throw "InstallRoot must name a directory, not a drive root."
    }
    if ($InstallRoot.Length -gt 37) {
        Write-Warning "The WinPython base directory is $($InstallRoot.Length) characters long. WinPython recommends about 37 characters or fewer; choose a shorter -InstallRoot if possible."
    }

    $installParent = [System.IO.Path]::GetDirectoryName($InstallRoot)
    [System.IO.Directory]::CreateDirectory($installParent) | Out-Null

    if ([System.IO.File]::Exists($InstallRoot)) { throw "Install target is an existing file: $InstallRoot" }
    if ([System.IO.Directory]::Exists($InstallRoot) -and -not $Force) {
        Write-Host "An installation already exists at: $InstallRoot"
        while ($true) {
            $answer = [string](Read-Host "Replace it? The existing installation will be retained as a timestamped backup [Y/n]")
            if ([string]::IsNullOrWhiteSpace($answer) -or $answer -match '^(?i:y|yes)$') { break }
            if ($answer -match '^(?i:n|no)$') {
                Write-Host "Installation cancelled. The existing installation was not changed."
                $exitCode = 0
                return
            }
            Write-Host "Enter Y or N. Press Enter to accept the default (Y)."
        }
    }

    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12
    do {
        $workRoot = Join-Path $installParent (".pcw-" + [System.Guid]::NewGuid().ToString('N').Substring(0, 8))
    } while ([System.IO.Directory]::Exists($workRoot) -or [System.IO.File]::Exists($workRoot))
    $downloadDirectory = Join-Path $workRoot "d"
    $stagingDirectory = Join-Path $workRoot "s"
    [System.IO.Directory]::CreateDirectory($downloadDirectory) | Out-Null
    [System.IO.Directory]::CreateDirectory($stagingDirectory) | Out-Null

    $localFixture = -not [string]::IsNullOrWhiteSpace($ConfigFile)
    $configPath = Join-Path $downloadDirectory "pythonCWMS_config.json"
    if ($localFixture) {
        if (-not [System.IO.File]::Exists($ConfigFile)) { throw "Configuration file not found: $ConfigFile" }
        [System.IO.File]::Copy([System.IO.Path]::GetFullPath($ConfigFile), $configPath, $false)
    }
    else {
        Write-Host "Downloading release configuration..."
        Get-HttpsFile $ConfigUrl $configPath $false
    }
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json

    $requiredFields = @('config_version', 'version', 'archive_filename', 'python_download_url', 'python_expected_hash_sha256', 'python_signature_url')
    foreach ($field in $requiredFields) {
        if (-not ($config.PSObject.Properties.Name -contains $field) -or [string]::IsNullOrWhiteSpace([string]$config.$field)) {
            throw "Configuration is missing required field '$field'."
        }
    }
    if ([int]$config.config_version -ne 2) { throw "Unsupported installer configuration version: $($config.config_version)" }
    if ([string]$config.version -notmatch '^\d+\.\d+(\.\d+)?$') { throw "Configuration contains an invalid version." }
    $archiveFilename = [string]$config.archive_filename
    if ([System.IO.Path]::GetFileName($archiveFilename) -ne $archiveFilename -or
        $archiveFilename -ne "pythonCWMS$($config.version).zip") {
        throw "Configuration contains an invalid archive filename."
    }
    if ([string]$config.python_expected_hash_sha256 -notmatch '^[0-9A-Fa-f]{64}$') {
        throw "Configuration contains an invalid SHA-256 hash."
    }
    Assert-DownloadSource ([string]$config.python_download_url) 'python_download_url' $localFixture
    Assert-DownloadSource ([string]$config.python_signature_url) 'python_signature_url' $localFixture
    if (-not $localFixture) {
        $archiveUri = [System.Uri]([string]$config.python_download_url)
        $signatureUri = [System.Uri]([string]$config.python_signature_url)
        if ([System.IO.Path]::GetFileName($archiveUri.AbsolutePath) -ne $archiveFilename -or
            [System.IO.Path]::GetFileName($signatureUri.AbsolutePath) -ne "$archiveFilename.sig") {
            throw "Configuration download filenames do not match archive_filename."
        }
    }

    $archivePath = Join-Path $downloadDirectory $archiveFilename
    $signaturePath = "$archivePath.sig"
    Write-Host "Downloading Python CWMS $($config.version)..."
    $downloadTimer = [System.Diagnostics.Stopwatch]::StartNew()
    Get-HttpsFile ([string]$config.python_download_url) $archivePath $localFixture
    Get-HttpsFile ([string]$config.python_signature_url) $signaturePath $localFixture
    $downloadTimer.Stop()
    $archiveSizeMiB = (Get-Item -LiteralPath $archivePath).Length / 1MB
    Write-Host ("Downloaded {0:N1} MiB in {1:N1} seconds." -f $archiveSizeMiB, $downloadTimer.Elapsed.TotalSeconds)

    Write-Host "Verifying archive hash and signature..."
    $verificationTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
    if ($actualHash -ne [string]$config.python_expected_hash_sha256) {
        throw "SHA-256 hash mismatch. The downloaded archive will not be installed."
    }

    $publicKeyPem = $ReleasePublicKeyPem
    if (-not [string]::IsNullOrWhiteSpace($PublicKeyFile)) {
        if (-not $localFixture) { throw "A test public key can only be used with a local configuration file." }
        $publicKeyPem = Get-Content -LiteralPath $PublicKeyFile -Raw
    }
    if (-not (Test-ArchiveSignature $archivePath $signaturePath $publicKeyPem $actualHash)) {
        throw "RSA signature verification failed. The archive will not be installed."
    }
    $verificationTimer.Stop()
    Write-Host ("Archive verified in {0:N1} seconds." -f $verificationTimer.Elapsed.TotalSeconds)

    Write-Host "Inspecting and extracting the archive..."
    $extractionTimer = [System.Diagnostics.Stopwatch]::StartNew()
    Expand-SafeZip $archivePath $stagingDirectory
    $extractionTimer.Stop()
    Write-Host ("Archive extracted in {0:N1} seconds." -f $extractionTimer.Elapsed.TotalSeconds)
    $stagedPythonExe = Join-Path $stagingDirectory "python\python.exe"
    if (-not [System.IO.File]::Exists($stagedPythonExe)) { throw "Archive is missing python\python.exe." }

    if ([System.IO.Directory]::Exists($InstallRoot)) {
        $backupPath = "$InstallRoot.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        if ([System.IO.Directory]::Exists($backupPath) -or [System.IO.File]::Exists($backupPath)) {
            $backupPath = "$backupPath-$([System.Guid]::NewGuid().ToString('N').Substring(0, 8))"
        }
        Write-Host "Moving the existing installation to: $backupPath"
        [System.IO.Directory]::Move($InstallRoot, $backupPath)
    }

    # Copy out of staging instead of renaming it. Endpoint protection can briefly
    # hold newly extracted executables open and deny a directory rename.
    Write-Host "Installing Python CWMS..."
    $installationTimer = [System.Diagnostics.Stopwatch]::StartNew()
    [System.IO.Directory]::CreateDirectory($InstallRoot) | Out-Null
    $installedTargetCreated = $true
    foreach ($item in Get-ChildItem -LiteralPath $stagingDirectory -Force) {
        Copy-Item -LiteralPath $item.FullName -Destination $InstallRoot -Recurse -Force
    }
    $installationTimer.Stop()
    Write-Host ("Files installed in {0:N1} seconds." -f $installationTimer.Elapsed.TotalSeconds)

    $pythonExe = Join-Path $InstallRoot "python\python.exe"
    Write-Host "Running the installed Python startup test..."
    & $pythonExe -c "import sys; print(sys.version)"
    if ($LASTEXITCODE -ne 0) { throw "The installed Python startup test failed with exit code $LASTEXITCODE." }

    $target = [System.EnvironmentVariableTarget]::User
    $oldHome = [System.Environment]::GetEnvironmentVariable("PYTHON_CWMS_HOME", $target)
    $oldPath = [System.Environment]::GetEnvironmentVariable("Path", $target)
    $environmentStarted = $true
    Set-UserEnvironment (Join-Path $InstallRoot "python") $oldHome

    Write-Host ""
    Write-Host "Python CWMS $($config.version) installed successfully at: $InstallRoot"
    if ($null -ne $backupPath) { Write-Host "Previous installation retained at: $backupPath" }
    Write-Host "PYTHON_CWMS_HOME was set to: $(Join-Path $InstallRoot 'python')"
    Write-Host "Close all terminal windows, then open a new one before using pythonCWMS."
    $exitCode = 0
}
catch {
    Write-Error $_.Exception.Message -ErrorAction Continue
    if ($environmentStarted) {
        try {
            $target = [System.EnvironmentVariableTarget]::User
            [System.Environment]::SetEnvironmentVariable("PYTHON_CWMS_HOME", $oldHome, $target)
            [System.Environment]::SetEnvironmentVariable("Path", $oldPath, $target)
        }
        catch { Write-Warning "Could not restore the previous user environment variables: $($_.Exception.Message)" }
    }
    if ($installedTargetCreated -and [System.IO.Directory]::Exists($InstallRoot)) {
        try { [System.IO.Directory]::Delete($InstallRoot, $true) }
        catch { Write-Warning "Could not remove the incomplete new installation: $($_.Exception.Message)" }
    }
    if ($null -ne $backupPath -and [System.IO.Directory]::Exists($backupPath) -and -not [System.IO.Directory]::Exists($InstallRoot)) {
        try {
            [System.IO.Directory]::Move($backupPath, $InstallRoot)
            Write-Host "The previous installation was restored."
            $backupPath = $null
        }
        catch { Write-Warning "Could not restore the backup at '$backupPath': $($_.Exception.Message)" }
    }
}
finally {
    if ($null -ne $workRoot -and [System.IO.Directory]::Exists($workRoot)) {
        try { [System.IO.Directory]::Delete($workRoot, $true) }
        catch { Write-Warning "Could not clean installer temporary directory '$workRoot': $($_.Exception.Message)" }
    }
}

exit $exitCode
