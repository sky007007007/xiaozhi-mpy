# xiaozhi-mpy：小智 ESP32-S3 MicroPython 固件

基于对第三方小智 MicroPython 固件的逆向分析，重建/自研一套跑在 ESP32-S3（N16R8）上的
MicroPython 小智固件，并通过 Git 自动化流程烧录到目标设备（"小程"机）。

参考项目：[genvex/xiaozhi-zyb](https://gitee.com/genvex/xiaozhi-zyb)（虾哥 xiaozhi-esp32 的 ESP-IDF/C++ 版，
提供小智协议、功能与板卡配置参考）。

## 目录结构

```
xiaozhi-mpy/
├── docs/                     # 逆向资料与开发文档
│   ├── 01-固件逆向报告.html   # 完整逆向分析报告（可视化）
│   ├── 02-固件身份与布局.md   # 固件指纹、flash 布局、段映射
│   ├── 03-mpy格式差异.md     # 私有 fork 的 mpy 编码差异（重建 .mpy 的关键）
│   ├── 04-模块清单.md        # 51 个冻结模块清单与定制模块说明
│   └── 05-路线图与自动化烧录.md # mpy 固件制作计划 + git 自动化烧录方案
├── firmware/                 # 原版参考固件（3MB，整包烧录 @ 0x0）
│   └── firmware_esp32s3_N16R8_xiaozhi.bin
├── extracted/                # 从固件重建的 51 个冻结模块 .mpy
├── disasm/                   # 对应的反汇编文本
├── tools/
│   ├── extract_mpy2.py       # 从固件 bin 提取冻结模块 -> 重建 .mpy
│   ├── mpy_tool.py           # mpy 反汇编/解析工具（已适配 fork 格式）
│   └── flash.py              # 一键烧录脚本（esptool 封装）
└── .gitignore
```

## 快速开始

### 1. 烧录原版参考固件（验证硬件与流程）

```bash
pip install esptool
python tools/flash.py --port COM5            # Windows
python tools/flash.py --port /dev/ttyUSB0    # Linux
```

### 2. 解析逆向出的模块

```bash
python tools/mpy_tool.py -d extracted/xiaozhi.py.mpy > xiaozhi.dis
```

## 固件关键信息（速查）

- MicroPython 1.30.0-preview，私有 fork（commit 8cb7558d00-dirty），ESP-IDF v5.5.3
- 芯片：ESP32-S3 N16R8；板卡定制模块：`xiaozhi/client/ovoui/ovomini/user/onboarding/wifinet`
- flash 布局：0x0 整包（bootloader + 主固件 7 段 + @0x290000 ESP-SR 唤醒词 wn9_nihaoxiaozhi_tts）
- qstr 编码 = `qst<<3 | 2`（与官方 `qst<<4|6` 不同）——详见 docs/03

## 自动化烧录

详见 [docs/05-路线图与自动化烧录.md](docs/05-路线图与自动化烧录.md)。
