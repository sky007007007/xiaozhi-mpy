#!/usr/bin/env python3
"""一键烧录小智固件到 ESP32-S3。

用法:
    python tools/flash.py                      # 自动探测串口, 烧 firmware/ 下的整包 bin
    python tools/flash.py --port COM5          # 指定串口
    python tools/flash.py --file my.bin        # 指定固件文件
    python tools/flash.py --baud 460800        # 慢速烧录(线材差时)
依赖: pip install esptool
"""
import argparse
import glob
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FW = os.path.join(HERE, "..", "firmware", "firmware_esp32s3_N16R8_xiaozhi.bin")


def find_port():
    """自动探测 ESP32-S3 串口 (CP210x / CH34x / JTAG-Serial)。"""
    import serial.tools.list_ports

    hints = ("cp210", "ch34", "usb serial", "jtag", "uart", "silicon labs", "wch")
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").lower()
        if any(h in desc for h in hints):
            return p.device
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if len(ports) == 1:
        return ports[0]
    sys.exit("无法自动探测串口, 请用 --port 指定。候选: " + ", ".join(ports))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", help="串口, 如 COM5 或 /dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--file", default=DEFAULT_FW, help="固件 bin 路径")
    ap.add_argument("--erase", action="store_true", help="烧录前整片擦除(慎用, 会清掉已配网信息)")
    args = ap.parse_args()

    fw = os.path.abspath(args.file)
    if not os.path.isfile(fw):
        sys.exit(f"固件不存在: {fw}")
    port = args.port or find_port()
    print(f"==> 端口: {port}  波特率: {args.baud}")
    print(f"==> 固件: {fw}  ({os.path.getsize(fw)} 字节, 整包 @ 0x0)")

    esptool = [sys.executable, "-m", "esptool"]
    cmds = []
    if args.erase:
        cmds.append(["erase_flash"])
    cmds.append(["--baud", str(args.baud), "--port", port, "write_flash", "0x0", fw])

    for cmd in cmds:
        r = subprocess.run(esptool + cmd)
        if r.returncode != 0:
            sys.exit(f"命令失败: {cmd}")
    print("==> 烧录完成。设备将重启进入小智。")


if __name__ == "__main__":
    main()
