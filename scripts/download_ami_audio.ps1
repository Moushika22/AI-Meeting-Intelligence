
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AudioDir = Join-Path $ProjectRoot "data\raw\ami\audio"
$ReportDir = Join-Path $ProjectRoot "data\interim\audio_quality"
$Manifest = Join-Path $ReportDir "download_manifest.csv"

New-Item -ItemType Directory -Force -Path $AudioDir | Out-Null
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

# Twelve recordings for the initial dataset.
$MeetingIds = @(
    "ES2002a", "ES2002b", "ES2002c", "ES2002d",
    "ES2003a", "ES2003b", "ES2003c", "ES2003d",
    "ES2004a", "ES2004b", "ES2004c", "ES2004d"
)

$BaseUrl = "https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/HeadsetAudio"
$Results = @()

foreach ($MeetingId in $MeetingIds) {
    $FileName = "$MeetingId.Mix-Headset.wav"
    $Destination = Join-Path $AudioDir $FileName
    $Url = "$BaseUrl/$FileName"

    Write-Host "`nProcessing $FileName" -ForegroundColor Cyan

    $Status = "FAILED"
    $ErrorMessage = ""

    if (Test-Path $Destination) {
        $Existing = Get-Item $Destination

        if ($Existing.Length -gt 1MB) {
            Write-Host "File already exists; skipping download."
            $Status = "EXISTS_CHECK_REQUIRED"
        }
    }

    if ($Status -eq "FAILED") {
        try {
            & curl.exe -L --fail `
                --retry 3 `
                --retry-delay 2 `
                --connect-timeout 30 `
                --output $Destination `
                $Url

            if ($LASTEXITCODE -ne 0) {
                throw "curl.exe exited with code $LASTEXITCODE"
            }

            if (-not (Test-Path $Destination)) {
                throw "Downloaded file was not created."
            }

            if ((Get-Item $Destination).Length -le 1MB) {
                throw "File is unexpectedly small; download may have failed."
            }

            $Status = "DOWNLOADED"
        }
        catch {
            $ErrorMessage = $_.Exception.Message
            $Status = "FAILED"

            if (Test-Path $Destination) {
                Remove-Item $Destination -Force
            }

            Write-Warning "Download failed for $MeetingId : $ErrorMessage"
        }
    }

    $FileSize = 0
    if (Test-Path $Destination) {
        $FileSize = (Get-Item $Destination).Length
    }

    $Results += [PSCustomObject]@{
        MeetingId = $MeetingId
        FileName = $FileName
        SourceURL = $Url
        Status = $Status
        SizeMB = [math]::Round($FileSize / 1MB, 2)
        Error = $ErrorMessage
    }

    Write-Host "Status: $Status | Size: $([math]::Round($FileSize / 1MB, 2)) MB"
}

$Results | Export-Csv -Path $Manifest -NoTypeInformation -Encoding UTF8

Write-Host "`nDOWNLOAD SUMMARY" -ForegroundColor Green
$Results | Format-Table MeetingId, Status, SizeMB -AutoSize

Write-Host "Manifest saved to: $Manifest"
Write-Host "Review any FAILED or EXISTS_CHECK_REQUIRED entries."
