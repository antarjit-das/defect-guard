[CmdletBinding()]
param(
    [switch]$NoConfirm
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

# Never allow a source template to be deployed: SAM build installs backend/
# requirements.txt into each Lambda's artifact directory, including Pydantic.
sam build --template-file infra/template.yaml
if ($LASTEXITCODE -ne 0) { throw "SAM build failed." }

$artifact = '.aws-sam/build/CreatePacketFunction'
$pydanticPackage = Join-Path $artifact 'pydantic'
$pydanticCore = Get-ChildItem -Path (Join-Path $artifact 'pydantic_core') -Filter '_pydantic_core*.so' -ErrorAction SilentlyContinue
if (-not (Test-Path $pydanticPackage) -or -not $pydanticCore) {
    throw "CreatePacketFunction artifact is missing the Pydantic Lambda dependency."
}
# The dependency is Linux-native, so do not import it with Windows Python here.
# Presence of both the package and pydantic-core's Lambda .so confirms the zip
# SAM will upload contains the complete Pydantic runtime dependency.
Write-Host "Verified CreatePacketFunction artifact includes Pydantic and pydantic-core."

$configFile = Join-Path $projectRoot 'samconfig.toml'
$deployArgs = @('deploy', '--template-file', '.aws-sam/build/template.yaml', '--config-file', $configFile)
if ($NoConfirm) { $deployArgs += '--no-confirm-changeset' }
sam @deployArgs
if ($LASTEXITCODE -ne 0) { throw "SAM deploy failed." }
