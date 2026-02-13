param(
  [string]$DriveLetter = "D:"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

(New-Object -ComObject Shell.Application).NameSpace(17).ParseName($DriveLetter).InvokeVerb("Eject")
Write-Host "Eject requested for $DriveLetter"
