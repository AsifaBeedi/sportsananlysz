param(
    [ValidateSet("smoke", "demo", "dashboard")]
    [string]$Mode = "demo",

    [ValidateSet("tennis", "cricket", "baseball", "hockey", "volleyball", "basketball")]
    [string]$Sport = "tennis",

    [int]$MaxFrames = 60,
    [int]$Port = 8501,
    [switch]$Headless,
    [switch]$NoOutputVideo,
    [ValidateSet("auto", "mp4v", "avc1", "h264", "none")]
    [string]$WriterCodec = "auto"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if ($Mode -eq "smoke") {
    & python tools\smoke_test.py --sport $Sport --max-frames 1 --dashboard-port $Port
    exit $LASTEXITCODE
}

if ($Mode -eq "demo") {
    $demoArgs = @(
        "src\main_pipeline.py",
        "--sport", $Sport,
        "--source-type", "demo",
        "--no-display",
        "--writer-codec", $WriterCodec,
        "--max-frames", $MaxFrames
    )
    if ($NoOutputVideo) {
        $demoArgs += "--no-output-video"
    }
    & python @demoArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

$streamlitArgs = @("-m", "streamlit", "run", "app\streamlit_app.py", "--server.port", "$Port")
if ($Headless) {
    $streamlitArgs += @("--server.headless", "true")
}

& python @streamlitArgs
exit $LASTEXITCODE
