# iHeartRadio Home Assistant Deployment Runner
param (
    [switch]$Help
)

$script = Join-Path $PSScriptRoot "deploy_ha.mjs"
node $script @args
