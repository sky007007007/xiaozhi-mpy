# 03 · 私有 fork 的 mpy 格式差异（逆向关键发现）

该固件使用一个**未公开的 MicroPython 私有 fork**，其 .mpy 持久化编码与官方存在多处差异。
自研固件若要兼容官方 mpy-cross 需注意：重建/编译出的 .mpy 必须匹配目标运行时的格式。

## 1. qstr 对象编码

- **fork**：`qst << 3 | 2`
- **官方**：`qst << 4 | 6`
- float 编码不变，且两者值域不重叠（可用于编码类型判别）。

## 2. mp_frozen_module_t 的 obj_table 可为 NULL

无独立对象表时写 NULL（重建时用 None 占位）。

## 3. 无子码的 rawcode

- 指针直接指向字节码，**没有** `{00 00 kind gen}` 头；
- 12 字节头仅存在于**有 children** 的 rawcode。

## 4. qstr 池结构

```
{prev, total_prev_len, alloc, len} + 2 个非 qstr 值 + 条目数组
```

- 条目为 4 字节指针，直接指向字符串；
- 池中包含中文 UTF-8 字符串（ovomini 的颜色名）；
- `0xFF` 开头的条目 = ROM 压缩文本。

## 5. 重建 .mpy 时的规则

- varint 为**大端 7-bit 组**；
- `n_qstr` 必须取各函数 prelude 里 simple_name / 参数名的最大索引；
- `n_obj` 用 `max(LOAD_CONST_OBJ) + 1`。

## 对自研固件的意义

两条路线（详见 docs/05）：

1. **路线 A（推荐起步）**：用官方 MicroPython 1.30-preview 自建固件，
   把逆向出的定制模块（xiaozhi.py 等）反汇编还原为 .py 源码后冻结进去；
   格式全部走官方编码，无需 fork。
2. **路线 B**：设法复用私有 fork 的运行时（从 bin 中无法拿到源码，
   只能整包复用原固件 + 替换可更新的冻结模块）。
