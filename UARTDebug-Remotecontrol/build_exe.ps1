<# 
.SYNOPSIS
    将 VESC-UART-RemoteControl 打包为单个 exe 文件

.DESCRIPTION
    使用 PyInstaller 将 Python GUI 程序打包为独立的 Windows 可执行文件
    支持 PySide6、pyserial 等依赖

.NOTES
    运行前请确保已安装 Python 和所需依赖
    首次运行会自动安装 PyInstaller
#>

param(
    [switch]$Clean = $false,      # 清理之前的构建产物
    [switch]$NoConsole = $true,   # 隐藏控制台窗口 (GUI 程序建议开启)
    [switch]$OneFile = $true,     # 打包为单个 exe
    [string]$Icon = ""            # 可选：指定 .ico 图标文件路径
)

# 设置工作目录为脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# 优先使用项目 venv 中的 Python（保证与 PySide6/pyserial 使用同一环境）
$Python = "python"
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $Python = $VenvPython
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  VESC-UART-RemoteControl 打包脚本" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python 环境
Write-Host "[1/5] 检查 Python 环境..." -ForegroundColor Yellow
Write-Host "    使用解释器: $Python" -ForegroundColor Gray
try {
    $pythonVersion = & $Python --version 2>&1
    Write-Host "    Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Error "未找到 Python，请先安装 Python 并添加到 PATH"
    exit 1
}

# 检查/安装 PyInstaller
Write-Host "[2/5] 检查 PyInstaller..." -ForegroundColor Yellow
try {
    & $Python -m PyInstaller --version 2>&1 | Out-Null
    Write-Host "    PyInstaller 已安装" -ForegroundColor Green
} catch {
    Write-Host "    正在安装 PyInstaller..." -ForegroundColor Yellow
    & $Python -m pip install pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller 安装失败"
        exit 1
    }
    Write-Host "    PyInstaller 安装完成" -ForegroundColor Green
}

# 清理旧构建
if ($Clean) {
    Write-Host "[3/5] 清理旧构建产物..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "build", "dist", "*.spec" -ErrorAction SilentlyContinue
    Write-Host "    清理完成" -ForegroundColor Green
} else {
    Write-Host "[3/5] 跳过清理 (使用 -Clean 参数可清理)" -ForegroundColor Yellow
}

# 构建 PyInstaller 参数
Write-Host "[4/5] 准备打包参数..." -ForegroundColor Yellow

$pyinstallerArgs = @(
    "main.py"
    "--name=VESC-UART-RemoteControl"
    "--clean"
    "--noconfirm"
)

if ($OneFile) {
    $pyinstallerArgs += "--onefile"
}

if ($NoConsole) {
    $pyinstallerArgs += "--noconsole"
}

if ($Icon -and (Test-Path $Icon)) {
    $pyinstallerArgs += "--icon=$Icon"
}

# 添加数据文件 (如果有配置文件等需要打包)
# $pyinstallerArgs += "--add-data=config.json;."

# 隐式导入：只放静态 import 识别不到的动态模块。
# 说明：
#   - 代码里 PySide6.QtCore/QtGui/QtWidgets 均为直接 import，PyInstaller 的
#     PySide6 hook 会自动收集所需插件与翻译，无需 hidden-import。
#   - 切勿再用 --collect-all=PySide6 / shiboken6：会把 QtWebEngine、QtQuick、
#     Qt3D、QtCharts 等全部模块连插件一起打包，导致 exe 膨胀到几百 MB。
$hiddenImports = @(
    "serial.tools.list_ports_windows"   # serial.tools.list_ports 按平台动态加载
)

foreach ($imp in $hiddenImports) {
    $pyinstallerArgs += "--hidden-import=$imp"
}

# 可选：若想进一步瘦身，可排除确定用不到的重型 Qt 模块（按需增删）
# $pyinstallerArgs += "--exclude-module=PySide6.QtWebEngineCore"
# $pyinstallerArgs += "--exclude-module=PySide6.QtWebEngineWidgets"

Write-Host "    参数: $($pyinstallerArgs -join ' ')" -ForegroundColor Gray

# 执行打包
Write-Host "[5/5] 开始打包..." -ForegroundColor Yellow
Write-Host ""

$startTime = Get-Date
& $Python -m PyInstaller @pyinstallerArgs
$exitCode = $LASTEXITCODE
$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "  打包成功！" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    
    $exePath = "dist\VESC-UART-RemoteControl.exe"
    if (Test-Path $exePath) {
        $size = (Get-Item $exePath).Length / 1MB
        Write-Host "输出文件: $exePath" -ForegroundColor Cyan
        Write-Host "文件大小: $([math]::Round($size, 2)) MB" -ForegroundColor Cyan
        Write-Host "耗时: $([math]::Round($duration.TotalSeconds, 1)) 秒" -ForegroundColor Cyan
    }
} else {
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "  打包失败 (退出码: $exitCode)" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    exit $exitCode
}

Write-Host ""
Write-Host "提示: 使用 -Clean 参数可清理构建缓存后重新打包" -ForegroundColor Gray