#!/usr/bin/env python3
"""从小智 MicroPython 固件提取冻结模块 -> 重建 .mpy (v2, 精确表长度)"""
import struct, os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("mpy_tool", os.path.join(HERE, "mpy_tool.py"))
mt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mt)

FW = r"D:/其他/Downloads/firmware_esp32s3_N16R8_xiaozhi (3).bin"
OUT = os.path.join(HERE, "extracted")
data = open(FW, "rb").read()

SEGS = [
    (0x3c1d0020, 0x6dcb0, 0x10020), (0x3fc9f500, 0x2340, 0x7dcd8),
    (0x42000020, 0x1c4418, 0x80020), (0x3fca1840, 0x4ee0, 0x244440),
    (0x40374000, 0x1b3fc, 0x249328), (0x50001000, 0x20, 0x26472c),
    (0x600fe000, 0x38, 0x264754),
]
DROM_HI = 0x7dcd8
def v2f(v):
    for load, ln, foff in SEGS:
        if load <= v < load + ln:
            return foff + (v - load)
    return None
def u32(f): return struct.unpack("<I", data[f:f+4])[0]
def u16(f): return struct.unpack("<H", data[f:f+2])[0]

# qstr 池: 结构 {prev,total_prev_len,alloc,len} + 2个非qstr值 + entries
POOLS = [(0x44dec, 0), (0x43228, 228), (0x5dc44, 1240)]
QSTR_MAP = {}
for soff, base in POOLS:
    ln = u32(soff + 12)
    eoff = soff + 24
    for i in range(ln):
        v = u32(eoff + 4*i)
        f = v2f(v)
        if f is None: continue
        e = data.find(b"\x00", f, f + 400)
        if e is None: continue
        s = data[f:e]
        if not s or s[0] == 0xFF:  # 跳过 ROM 压缩文本(0xFF 前缀)
            continue
        QSTR_MAP[base + i] = s
print("qstr mapped:", len(QSTR_MAP))

NAMES = ["_boot.py","flashbdev.py","inisetup.py","machine.py","pinutil.py","ssd1306.py","ovoui.py","user.py","xiaozhi.py","wifinet.py","client.py","onboarding.py","bmp280.py","mpu6050.py","hcsr04.py","pn532.py","hx711.py","DS1302.py","sdcard.py","espnow.py","simple.py","hid_services.py","webrepl_cfg.py","tm1637.py","i2c_lcd.py","lcd_api.py","boot.py","ovomini.py","ir_rx/sony.py","ir_rx/mce.py","ir_rx/nec.py","ir_rx/philips.py","ir_rx/__init__.py","ir_rx/print_error.py","ir_rx/acquire.py","ir_rx/test.py","asyncio/__init__.py","asyncio/core.py","asyncio/event.py","asyncio/funcs.py","asyncio/lock.py","asyncio/stream.py","uasyncio.py","umqtt/robust.py","ssl.py","umqtt/simple.py","upysh.py","requests/__init__.py","mip/__init__.py","ntptime.py","neopixel.py"]
ARR = 0x49b70
modules = []
for i, name in enumerate(NAMES):
    sv = u32(ARR + 4*i)
    f = v2f(sv)
    qt, ot, pf = struct.unpack("<III", data[f:f+12])
    modules.append({"name": name, "qt": qt, "ot": ot, "pf": pf})

def is_rawcode_ptr(v):
    f = v2f(v)
    return f is not None and data[f] == 0 and data[f+1] == 0 and data[f+2] in (2,3,4,5) and data[f+3] in (0,1)

def walk_bc(fd):
    """解析 prelude + 遍历 opcode; -> (fun_len, max_q, max_o, max_c)"""
    bc = data[fd:DROM_HI]
    pre = mt.extract_prelude(bc, 0)
    ip = pre[4]
    # prelude 中的 simple_name/参数名也是 qstr 索引, 必须计入 max_q
    max_q = max(pre[7]) if pre[7] else 0
    max_o = max_c = 0
    while ip < len(bc):
        fmt, sz, arg, _ = mt.mp_opcode_decode(bc, ip)
        op = bc[ip]
        if fmt == mt.MP_BC_FORMAT_QSTR:
            if arg > 2943: return None
            max_q = max(max_q, arg)
        if op == mt.Opcode.MP_BC_LOAD_CONST_OBJ:
            max_o = max(max_o, arg)
        if op in (mt.Opcode.MP_BC_MAKE_FUNCTION, mt.Opcode.MP_BC_MAKE_FUNCTION_DEFARGS):
            max_c = max(max_c, arg)
        ip += sz
        if op == mt.Opcode.MP_BC_RETURN_VALUE:
            return (ip, max_q, max_o, max_c)
        if ip > 400000: return None
    return None

def get_code(pf_v):
    """-> (fun_data_file, kind, children_ptr_list)"""
    f = v2f(pf_v)
    if f is None: return None
    if is_rawcode_ptr(pf_v):
        kind = data[f+2]
        fd, ch = struct.unpack("<II", data[f+4:f+12])
        kids = []
        if ch:
            cf = v2f(ch)
            if cf is not None:
                kids = [u32(cf + 4*j) for j in range(512)]
        return (v2f(fd), kind, kids)
    if data[f] != 0 or data[f+1] != 0:
        if walk_bc(f): return (f, 2, [])
    return None

def emit_code(pf_v, stats, depth=0):
    gd = get_code(pf_v)
    if gd is None:
        raise Exception("bad code %#x" % pf_v)
    fd, kind, kids = gd
    if kind != 2:
        raise Exception("native kind=%d @%#x" % (kind, pf_v))
    r = walk_bc(fd)
    if r is None:
        raise Exception("walk failed @%#x" % fd)
    fun_len, max_q, max_o, max_c = r
    stats["max_q"] = max(stats["max_q"], max_q)
    stats["max_o"] = max(stats["max_o"], max_o)
    stats["max_c"] = max(stats["max_c"], max_c)
    n_children = max_c + 1 if kids else 0
    hdr = enc_varint((fun_len << 3) | ((1 << 2) if n_children else 0))
    out = bytearray(hdr)
    out += data[fd:fd+fun_len]
    if n_children:
        out += enc_varint(n_children)
        for j in range(n_children):
            out += emit_code(kids[j], stats, depth+1)
    return bytes(out)

def enc_varint(value):
    """MicroPython varint: 大端 7-bit 组, 除最后字节外每字节最高位置 1"""
    if value == 0:
        return b"\x00"
    groups = []
    while value:
        groups.append(value & 0x7F)
        value >>= 7
    groups.reverse()
    out = bytearray(groups)
    for i in range(len(out) - 1):
        out[i] |= 0x80
    return bytes(out)

def enc_qstr(s):
    return enc_varint(len(s) << 1) + s + b"\x00"

TYPE_NAMES = {}
def type_name(tp):
    if tp in TYPE_NAMES: return TYPE_NAMES[tp]
    f = v2f(tp)
    tn = None
    if f is not None:
        tn = QSTR_MAP.get(u16(f + 6))
    TYPE_NAMES[tp] = tn
    return tn

def decode_obj(v, stats):
    # fork 修改版 repr C 编码:
    #   small int: bit0=1 (v>>1)
    #   qstr:      (v&7)==2 且 v < 0x5C20  -> qstr = v>>3   (fork: qst<<3|2)
    #   immediate: (v&0xff80000f)==0xe
    #   float:     (v&3)==2 且 v >= 0x800002 (与 qstr 值域不重叠)
    #   指针:      (v&3)==0
    if v & 1:
        sv = v if v < 0x80000000 else v - (1 << 32)
        return ("INT", str(sv >> 1).encode())
    if (v & 7) == 2 and v < 0x5C20:
        q = v >> 3
        return ("STR", QSTR_MAP.get(q, b"q%d" % q))
    if (v & 0xff80000f) == 0xe:
        imm = v >> 4
        return {0:("NONE",None),1:("FALSE",None),2:("TRUE",None),4:("ELLIPSIS",None)}.get(imm,("NONE",None))
    if (v & 3) == 2 and (v & 0xff800007) != 6:
        bits = ((v - 0x80800000) & ~3) & 0xFFFFFFFF
        bits |= (bits >> 2) & 3
        fv = struct.unpack("<f", struct.pack("<I", bits))[0]
        return ("FLOAT", repr(fv).encode())
    if (v & 3) == 0:
        f = v2f(v)
        if f is None: return ("NONE", None)
        tn = type_name(u32(f)) or b""
        if tn in (b"str", b"bytes", b"bytearray"):
            ln = u32(f + 8); dp = u32(f + 12); df = v2f(dp)
            return ("STR" if tn == b"str" else "BYTES", data[df:df+ln] if df is not None and ln < 8192 else b"")
        if tn == b"tuple":
            tln = u32(f + 4)
            items = [decode_obj(u32(f + 8 + 4*j), stats) for j in range(tln)]
            return ("TUPLE", items)
        if tn == b"int":
            neg = u32(f + 4) & 1
            ln_ = u32(f + 12); dp = u32(f + 16); df = v2f(dp)
            val = 0
            if df is not None and 0 < ln_ < 64:
                for j in range(ln_):
                    val |= u32(df + 4*j) << (30 * j)
            return ("INT", str(-val if neg else val).encode())
        if tn == b"float":
            bits = u32(f + 4)
            fv = struct.unpack("<f", struct.pack("<I", bits))[0]
            return ("FLOAT", repr(fv).encode())
        stats["unknown_types"].add(tn)
        return ("NONE", None)
    return ("NONE", None)

TAGS = {"NONE":1,"FALSE":2,"TRUE":3,"ELLIPSIS":4,"STR":5,"BYTES":6,"INT":7,"FLOAT":8,"TUPLE":10}
def enc_obj(dec, depth=0):
    tag, payload = dec
    if tag in ("NONE","FALSE","TRUE","ELLIPSIS"):
        return bytes([TAGS[tag]])
    if tag == "TUPLE":
        if depth >= 4: return bytes([1])
        out = bytes([TAGS["TUPLE"]]) + enc_varint(len(payload))
        for it in payload:
            out += enc_obj(it, depth+1)
        return out
    out = bytes([TAGS[tag]]) + enc_varint(len(payload)) + payload
    if tag in ("STR","BYTES"):
        out += b"\x00"
    return out

os.makedirs(OUT, exist_ok=True)
results = []
for m in modules:
    name = m["name"]
    stats = {"max_q": 0, "max_o": 0, "max_c": 0, "unknown_types": set()}
    try:
        # 第一遍: 收集精确表大小
        emit_code(m["pf"], stats)
        n_qstr = stats["max_q"] + 1
        n_obj = stats["max_o"] + 1
        qtf = v2f(m["qt"])
        body = bytearray(b"M" + bytes([6, 0, 31]))
        body += enc_varint(n_qstr) + enc_varint(n_obj)
        for i in range(n_qstr):
            q = u16(qtf + 2*i)
            body += enc_qstr(QSTR_MAP.get(q, b"q%d" % q))
        if m["ot"]:
            otf = v2f(m["ot"])
            for i in range(n_obj):
                body += enc_obj(decode_obj(u32(otf + 4*i), stats))
        elif n_obj >= 1:
            # fork: ot=NULL 表示无独立 obj 表, 常量引用按 None 占位
            print("WARN: %s ot=NULL but %d obj refs -> placeholders" % (name, n_obj))
            for i in range(n_obj):
                body += enc_obj(("NONE", None))
        body += emit_code(m["pf"], stats)
        outp = os.path.join(OUT, name.replace("/", "_")) + ".mpy"
        open(outp, "wb").write(bytes(body))
        results.append((name, n_qstr, stats["max_q"], n_obj, stats["max_o"], len(body), sorted(stats["unknown_types"])))
    except Exception as ex:
        results.append((name, "", "", "", "", "", repr(ex)))

for r in results:
    print(r)
