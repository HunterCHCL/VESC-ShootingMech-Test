# VESC 射击机构 UART 遥控器

基于 Python / PySide6 的 PC 端遥控工具，用于通过 UART 控制固件
`VESC-ShootingMech-Test` 中的 6 路 VESC 射击电机（2 组：R1/R2/R3 与 F1/F2/F3）。
UI 与部分功能参考 `2026-RoboCup/UARTDebug-RemoteControl`。

## 运行

```bash
pip install -r requirements.txt
python main.py
```

依赖：`PySide6>=6.6`、`pyserial>=3.5`。

## 功能

- **串口连接**：枚举串口、选择波特率、打开/关闭/重连，显示 TX/RX 计数。
- **六路目标控制**：按 2 组 × 3 轮分组（第 1 组 V1~V3、第 2 组 V4~V6），每路可
  独立设置目标转速并选择是否启用；未启用的电机按 0 发送。每组提供「3轮同步」
  勾选框（默认勾选：改任意一路，整组 3 路目标自动保持一致）。
- **显示单位（ERPM / RPM）**：设置页可切换 UI 显示单位（换算关系 7 ERPM = 1 RPM），
  目标/实测读数、曲线与日志都会按所选单位显示；发送与接收的数据始终为 ERPM
  （通信协议不变）。
- **发送方式**：
  - `持续发送`：按设定周期（默认 200ms）重复发送当前目标。由于 MCU 看门狗为
    1s（超过 1s 未收到命令目标自动清零），调试/试车时建议开启持续发送。
  - `发送一次`：只发送当前目标一次。
  - `全部急停`：清空目标并立即发送全 0（也可按 `Esc`，需在“控制”页且不在输入框内）。
- **实时监听**：MCU 每 100ms 回传 6 路实测转速（ERPM），按当前显示单位显示大字
  数值、实时曲线与滚动日志。
- **配置持久化**：窗口位置、最近串口、波特率、六路目标与启用状态保存在项目根目录
  `settings.json`，可手动查看/备份/迁移。

## 通信协议（与固件 UARTDebug.c/.h 一致）

```
帧格式： [0xFA][0xAF][cmd][payload...][checksum]
checksum：除最后一个字节外所有字节之和，取低 8 位
```

**PC -> MCU（命令）**

| cmd | 含义 | payload |
|-----|------|---------|
| `0x01` | VESC_UPDATE | 6 × float32（小端）= vesc1..vesc6 目标 erpm，共 24 字节 |

完整帧 28 字节：`FA AF 01 <24B 数据> <校验>`。

**MCU -> PC（状态，每 100ms）**

```
FA AF <6 × float32 erpm> <校验>
```

注意：该状态帧**不含命令字节**。

## 兼容性说明（固件 off-by-one 已修复）

早期固件 `UARTDebug_SendFrame` 用 `UARTDebug_SendData(frame, len + 2)` 发送帧，
校验和字节会覆盖最后一个 payload 字节（第 6 个浮点的最高字节），导致状态帧仅
26 字节、第 6 路 VESC 的实测 erpm 损坏。该缺陷已在
`UserLib/UARTDebug/UARTDebug.c` 中修复：

- 发送帧改为 `len + 3` 字节，校验和置于 `frame[len + 2]`（状态帧现为 27 字节，
  6 路 erpm 全部有效）；
- 接收侧 `memcpy` 长度由 `len - 3` 修正为 `len - 4`，最小帧长守卫改为 `len < 4`。

本软件解析器同时支持 26 字节（旧固件）与 27 字节（修复后）两种帧，靠校验和
自动判别，新旧固件均可直接使用，无需改软件。

## 目录结构

```
UARTDebug-Remotecontrol/
├── main.py                    # 入口
├── requirements.txt
├── README.md
├── settings.json              # 运行时生成
└── remote_control/
    ├── __init__.py
    ├── app_settings.py        # settings.json 读写（原子替换）
    ├── config.py              # 配置访问接口
    ├── protocol.py            # 帧编解码 + 流解析器
    ├── serial_link.py         # 串口后台读写线程
    ├── main_window.py         # 主窗口
    └── ui/
        ├── control_panel.py   # 六路目标 + 发送控制
        ├── monitor_panel.py   # 实时监听
        └── live_plot.py       # 轻量实时曲线（QPainter，无第三方依赖）
```
