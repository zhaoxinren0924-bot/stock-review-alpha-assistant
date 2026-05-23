param(
    [string]$FrontendBaseUrl = "http://127.0.0.1:5173",
    [string]$StockCode = "300308"
)

$ErrorActionPreference = "Stop"

function Invoke-Json {
    param(
        [string]$Uri,
        [string]$Method = "GET",
        [object]$Body = $null
    )

    $params = @{
        Uri = $Uri
        Method = $Method
        UseBasicParsing = $true
    }

    if ($null -ne $Body) {
        $params.ContentType = "application/json; charset=utf-8"
        $params.Body = ($Body | ConvertTo-Json -Depth 10)
    }

    $response = Invoke-WebRequest @params
    if ([string]::IsNullOrWhiteSpace($response.Content)) {
        return $null
    }
    return $response.Content | ConvertFrom-Json
}

Write-Host "1. Checking frontend is reachable..."
Invoke-WebRequest -UseBasicParsing $FrontendBaseUrl | Out-Null

Write-Host "2. Checking stocks API through Vite proxy..."
$stocks = Invoke-Json "$FrontendBaseUrl/api/v1/stocks"
if ($stocks.count -lt 1) {
    throw "No stocks found. Add at least one stock before checking the AI panel."
}

$stock = $stocks.items | Where-Object { $_.code -eq $StockCode } | Select-Object -First 1
if ($null -eq $stock) {
    $stock = $stocks.items | Select-Object -First 1
    $StockCode = $stock.code
}

Write-Host "3. Refreshing data and checking evidence API for $StockCode..."
$refresh = Invoke-Json "$FrontendBaseUrl/api/v1/stocks/$StockCode/data/refresh" "POST" @{
    types = @("announcement", "news", "quote", "metric")
    lookback_days = 30
}
if ($null -eq $refresh.created -or $null -eq $refresh.skipped -or $null -eq $refresh.errors) {
    throw "Data refresh response is missing created/skipped/errors."
}

$evidence = Invoke-Json "$FrontendBaseUrl/api/v1/stocks/$StockCode/evidence"
if ($null -eq $evidence.items) {
    throw "Evidence endpoint did not return items."
}

Write-Host "4. Generating AI pending action for $StockCode..."
$chat = Invoke-Json "$FrontendBaseUrl/api/v1/ai/chat" "POST" @{
    stock_code = $StockCode
    message = "我看好 AI 算力链，帮我整理成可验证假设"
    history = @()
}

if ([string]::IsNullOrWhiteSpace($chat.reply)) {
    throw "AI chat did not return reply."
}
if ($null -eq $chat.actions -or $chat.actions.Count -lt 1) {
    throw "AI chat did not return pending actions."
}
if ($null -eq $chat.evidence_cards) {
    throw "AI chat response is missing evidence_cards."
}

Write-Host "5. Applying first pending action..."
$action = $chat.actions | Select-Object -First 1
$action.payload | Add-Member -NotePropertyName stock_code -NotePropertyValue $StockCode -Force
$apply = Invoke-Json "$FrontendBaseUrl/api/v1/ai/actions/apply" "POST" $action
if ($apply.type -ne $action.type) {
    throw "Apply action returned unexpected type."
}

Write-Host "6. Checking hypotheses refresh target..."
$hypotheses = Invoke-Json "$FrontendBaseUrl/api/v1/stocks/$StockCode/hypotheses"
if ($hypotheses.count -lt 1) {
    throw "Hypothesis list did not contain saved AI result."
}

Write-Host "AI right panel smoke check passed for $StockCode."
