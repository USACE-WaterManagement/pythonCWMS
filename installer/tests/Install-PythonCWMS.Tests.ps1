$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$Installer = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\Install-PythonCWMS.ps1'))
$TestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("PythonCWMS-Tests-" + [guid]::NewGuid().ToString('N'))
$EnvironmentTarget = [System.EnvironmentVariableTarget]::User
$OldHome = [System.Environment]::GetEnvironmentVariable('PYTHON_CWMS_HOME', $EnvironmentTarget)
$OldPath = [System.Environment]::GetEnvironmentVariable('Path', $EnvironmentTarget)

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "TEST FAILED: $Message" }
}

function Join-Bytes {
    param([object[]]$Arrays)
    $list = New-Object System.Collections.Generic.List[byte]
    foreach ($array in $Arrays) { foreach ($value in $array) { $list.Add([byte]$value) } }
    return $list.ToArray()
}

function Get-DerLength {
    param([int]$Length)
    if ($Length -lt 128) { return [byte[]]@([byte]$Length) }
    $bytes = New-Object System.Collections.Generic.List[byte]
    while ($Length -gt 0) { $bytes.Insert(0, [byte]($Length -band 0xff)); $Length = $Length -shr 8 }
    return Join-Bytes @([byte[]]@([byte](0x80 -bor $bytes.Count)), $bytes.ToArray())
}

function Get-DerValue {
    param([byte]$Tag, [byte[]]$Value)
    return Join-Bytes @([byte[]]@($Tag), (Get-DerLength $Value.Length), $Value)
}

function Get-DerInteger {
    param([byte[]]$Value)
    if (($Value[0] -band 0x80) -ne 0) { $Value = Join-Bytes @([byte[]]@(0), $Value) }
    return Get-DerValue 0x02 $Value
}

function Export-TestPublicKeyPem {
    param([System.Security.Cryptography.RSAParameters]$Parameters, [string]$Path)
    $rsaSequence = Get-DerValue 0x30 (Join-Bytes @((Get-DerInteger $Parameters.Modulus), (Get-DerInteger $Parameters.Exponent)))
    $algorithmIdentifier = [byte[]](0x30,0x0d,0x06,0x09,0x2a,0x86,0x48,0x86,0xf7,0x0d,0x01,0x01,0x01,0x05,0x00)
    $bitString = Get-DerValue 0x03 (Join-Bytes @([byte[]]@(0), $rsaSequence))
    $spki = Get-DerValue 0x30 (Join-Bytes @($algorithmIdentifier, $bitString))
    $base64 = [Convert]::ToBase64String($spki, [Base64FormattingOptions]::InsertLineBreaks)
    [IO.File]::WriteAllText($Path, "-----BEGIN PUBLIC KEY-----`r`n$base64`r`n-----END PUBLIC KEY-----`r`n")
}

function New-TestArchive {
    param([string]$Path, [switch]$Traversal)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if ($Traversal) {
        $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew)
        $zip = New-Object IO.Compression.ZipArchive($stream, [IO.Compression.ZipArchiveMode]::Create)
        try {
            $entry = $zip.CreateEntry('../escape.txt')
            $writer = New-Object IO.StreamWriter($entry.Open())
            try { $writer.Write('unsafe') } finally { $writer.Dispose() }
        } finally { $zip.Dispose(); $stream.Dispose() }
        return
    }

    $payload = Join-Path $TestRoot ("payload-" + [guid]::NewGuid().ToString('N'))
    $pythonDirectory = Join-Path $payload 'python'
    [IO.Directory]::CreateDirectory($pythonDirectory) | Out-Null
    $source = @'
public static class Program {
    public static int Main(string[] args) { return 0; }
}
'@
    Add-Type -TypeDefinition $source -Language CSharp -OutputType ConsoleApplication -OutputAssembly (Join-Path $pythonDirectory 'python.exe')
    [IO.Compression.ZipFile]::CreateFromDirectory($payload, $Path, [IO.Compression.CompressionLevel]::Optimal, $false)
}

function Write-TestConfig {
    param([string]$Path, [string]$Archive, [string]$Signature, [string]$Hash)
    [ordered]@{
        config_version = 2
        version = '2.0'
        archive_filename = 'pythonCWMS2.0.zip'
        python_download_url = $Archive
        python_expected_hash_sha256 = $Hash
        python_signature_url = $Signature
    } | ConvertTo-Json | Out-File $Path -Encoding utf8
}

function Invoke-InstallerTest {
    param([string]$Config, [string]$Target, [switch]$Force, [string]$PromptResponse)
    $arguments = @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Installer,
        '-InstallRoot', $Target, '-ConfigFile', $Config, '-PublicKeyFile', $script:PublicKeyPath)
    if ($Force) { $arguments += '-Force' }

    # PowerShell 5.1 turns a native process's stderr into error records. Several
    # tests intentionally make the installer fail, so capture those records
    # without allowing the script-wide Stop preference to abort the test run.
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        if ($PSBoundParameters.ContainsKey('PromptResponse')) {
            $output = $PromptResponse | & powershell.exe @arguments 2>&1 | Out-String
        }
        else {
            $output = & powershell.exe @arguments 2>&1 | Out-String
        }
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return @{ ExitCode = $exitCode; Output = $output }
}

try {
    [IO.Directory]::CreateDirectory($TestRoot) | Out-Null

    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($Installer, [ref]$tokens, [ref]$parseErrors)
    Assert-True ($parseErrors.Count -eq 0) "PowerShell 5.1 parser errors: $($parseErrors -join '; ')"
    Write-Host 'PASS: PowerShell syntax'

    $rsa = New-Object Security.Cryptography.RSACryptoServiceProvider(2048)
    $rsa.PersistKeyInCsp = $false
    $script:PublicKeyPath = Join-Path $TestRoot 'test-public.pem'
    Export-TestPublicKeyPem ($rsa.ExportParameters($false)) $script:PublicKeyPath

    $archive = Join-Path $TestRoot 'pythonCWMS2.0.zip'
    New-TestArchive $archive
    $hash = (Get-FileHash $archive -Algorithm SHA256).Hash
    $signature = "$archive.sig"
    $signatureBytes = $rsa.SignData([IO.File]::ReadAllBytes($archive), [Security.Cryptography.CryptoConfig]::MapNameToOID('SHA256'))
    [IO.File]::WriteAllBytes($signature, $signatureBytes)

    $config = Join-Path $TestRoot 'config.json'
    Write-TestConfig $config $archive $signature ('0' * 64)
    $result = Invoke-InstallerTest $config (Join-Path $TestRoot 'hash-target')
    Assert-True ($result.ExitCode -ne 0 -and $result.Output -match 'hash mismatch') 'Hash mismatch was not rejected.'
    Write-Host 'PASS: hash mismatch rejection'

    Write-TestConfig $config $archive (Join-Path $TestRoot 'missing.sig') $hash
    $result = Invoke-InstallerTest $config (Join-Path $TestRoot 'missing-signature-target')
    Assert-True ($result.ExitCode -ne 0) 'Missing signature was not rejected.'
    Write-Host 'PASS: missing signature rejection'

    $invalidSignature = Join-Path $TestRoot 'invalid.sig'
    [IO.File]::WriteAllBytes($invalidSignature, [byte[]](1,2,3,4))
    Write-TestConfig $config $archive $invalidSignature $hash
    $result = Invoke-InstallerTest $config (Join-Path $TestRoot 'invalid-signature-target')
    Assert-True ($result.ExitCode -ne 0 -and $result.Output -match 'signature verification failed') 'Invalid signature was not rejected.'
    Write-Host 'PASS: invalid signature rejection'

    $traversalArchive = Join-Path $TestRoot 'traversal.zip'
    New-TestArchive $traversalArchive -Traversal
    $traversalHash = (Get-FileHash $traversalArchive -Algorithm SHA256).Hash
    $traversalSignature = "$traversalArchive.sig"
    [IO.File]::WriteAllBytes($traversalSignature, $rsa.SignData([IO.File]::ReadAllBytes($traversalArchive), [Security.Cryptography.CryptoConfig]::MapNameToOID('SHA256')))
    Write-TestConfig $config $traversalArchive $traversalSignature $traversalHash
    $result = Invoke-InstallerTest $config (Join-Path $TestRoot 'traversal-target')
    Assert-True ($result.ExitCode -ne 0 -and $result.Output -match 'Unsafe ZIP entry') 'ZIP traversal was not rejected.'
    Assert-True (-not (Test-Path (Join-Path $TestRoot 'escape.txt'))) 'Traversal entry escaped staging.'
    Write-Host 'PASS: ZIP path traversal rejection'

    Write-TestConfig $config $archive $signature $hash
    $existingTarget = Join-Path $TestRoot 'existing-target'
    [IO.Directory]::CreateDirectory($existingTarget) | Out-Null
    [IO.File]::WriteAllText((Join-Path $existingTarget 'marker.txt'), 'preserve')
    $result = Invoke-InstallerTest $config $existingTarget -PromptResponse 'N'
    Assert-True ($result.ExitCode -eq 0 -and
        (Test-Path (Join-Path $existingTarget 'marker.txt')) -and
        $result.Output -match 'Installation cancelled') 'Declining replacement did not preserve the existing directory.'
    Write-Host 'PASS: existing-directory replacement declined'

    $promptTarget = Join-Path $TestRoot 'prompt-target'
    [IO.Directory]::CreateDirectory($promptTarget) | Out-Null
    [IO.File]::WriteAllText((Join-Path $promptTarget 'marker.txt'), 'preserve')
    $result = Invoke-InstallerTest $config $promptTarget -PromptResponse ''
    $promptBackup = @(Get-ChildItem $TestRoot -Directory -Filter 'prompt-target.backup-*')
    Assert-True ($result.ExitCode -eq 0 -and
        (Test-Path (Join-Path $promptTarget 'python\python.exe')) -and
        $promptBackup.Count -eq 1 -and
        (Test-Path (Join-Path $promptBackup[0].FullName 'marker.txt'))) "Confirmed fixture replacement failed: $($result.Output)"
    Write-Host 'PASS: existing-directory replacement defaults to yes'

    [Environment]::SetEnvironmentVariable('PYTHON_CWMS_HOME', $OldHome, $EnvironmentTarget)
    [Environment]::SetEnvironmentVariable('Path', $OldPath, $EnvironmentTarget)

    $legacyHome = Join-Path $TestRoot 'legacy\pythonCWMS\python'
    $pathBeforeMigration = [Environment]::GetEnvironmentVariable('Path', $EnvironmentTarget)
    [Environment]::SetEnvironmentVariable('PYTHON_CWMS_HOME', $legacyHome, $EnvironmentTarget)
    [Environment]::SetEnvironmentVariable(
        'Path', "$legacyHome;$legacyHome\Scripts;$pathBeforeMigration", $EnvironmentTarget)

    $successTarget = Join-Path $TestRoot 'success-target'
    $result = Invoke-InstallerTest $config $successTarget
    Assert-True ($result.ExitCode -eq 0 -and (Test-Path (Join-Path $successTarget 'python\python.exe'))) "Fixture install failed: $($result.Output)"
    Write-Host 'PASS: successful small-fixture installation'

    $result = Invoke-InstallerTest $config $successTarget -Force
    Assert-True ($result.ExitCode -eq 0) "Forced fixture reinstall failed: $($result.Output)"
    $environmentKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment')
    try {
        $userPath = [string]$environmentKey.GetValue(
            'Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $pathKind = $environmentKey.GetValueKind('Path')
    }
    finally {
        $environmentKey.Dispose()
    }
    $userPathParts = @($userPath.Split(';') | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $homeEntries = @($userPathParts | Where-Object { $_.TrimEnd([char[]]'\') -eq '%PYTHON_CWMS_HOME%' })
    $scriptsEntries = @($userPathParts | Where-Object { $_.TrimEnd([char[]]'\') -eq '%PYTHON_CWMS_HOME%\Scripts' })
    $legacyEntries = @($userPathParts | Where-Object { $_.TrimEnd([char[]]'\') -like "$legacyHome*" })
    Assert-True ($pathKind -eq [Microsoft.Win32.RegistryValueKind]::ExpandString) 'User PATH does not preserve environment-variable expansion.'
    Assert-True ($userPathParts[0] -eq '%PYTHON_CWMS_HOME%' -and $userPathParts[1] -eq '%PYTHON_CWMS_HOME%\Scripts') 'Python CWMS entries are not first in the user PATH.'
    Assert-True ($homeEntries.Count -eq 1 -and $scriptsEntries.Count -eq 1) 'PATH entries are not idempotent.'
    Assert-True ($legacyEntries.Count -eq 0) 'Legacy Python CWMS PATH entries were not removed.'
    Write-Host 'PASS: PATH migration and idempotent updates'

    $rsa.Dispose()
    Write-Host 'All Windows installer checks passed.'
}
finally {
    [Environment]::SetEnvironmentVariable('PYTHON_CWMS_HOME', $OldHome, $EnvironmentTarget)
    [Environment]::SetEnvironmentVariable('Path', $OldPath, $EnvironmentTarget)
    if (Test-Path $TestRoot) { [IO.Directory]::Delete($TestRoot, $true) }
}
