"""Tegra X1 block-linear (GOB 64B x 8행) 배치 해제/적용. 단위는 '원소'(ASTC 블록 16B)."""
import numpy as np


def _div(a, b):
    return (a + b - 1) // b


def deswizzle(data, w_el, h_el, bpe, block_height):
    """data: swizzled bytes, w_el/h_el: 원소 단위 크기. 반환 linear bytes (행 우선)."""
    pitch = w_el * bpe
    gobs_x = _div(pitch, 64)
    gob_rows = _div(h_el, 8)
    bh = block_height
    out = bytearray(pitch * h_el)
    src = memoryview(data)
    # 원소마다 주소 계산(벡터화)
    ys, xs = np.mgrid[0:h_el, 0:w_el]
    xb = xs * bpe
    gob_y = ys // 8
    block = gob_y // bh
    gob_in_block = gob_y % bh
    gob_x = xb // 64
    addr = (block * gobs_x * bh * 512
            + gob_x * bh * 512
            + gob_in_block * 512
            + ((xb % 64) // 32) * 256
            + ((ys % 8) // 2) * 64
            + ((xb % 32) // 16) * 32
            + (ys % 2) * 16
            + (xb % 16))
    a = np.frombuffer(bytes(data), np.uint8)
    lin = np.empty((h_el, w_el, bpe), np.uint8)
    for k in range(bpe):
        idx = addr + k
        ok = idx < len(a)
        lin[..., k] = np.where(ok, a[np.minimum(idx, len(a) - 1)], 0)
    return lin.tobytes()


def swizzle(linear, w_el, h_el, bpe, block_height, size):
    ys, xs = np.mgrid[0:h_el, 0:w_el]
    pitch = w_el * bpe
    gobs_x = _div(pitch, 64)
    bh = block_height
    xb = xs * bpe
    gob_y = ys // 8
    addr = ((gob_y // bh) * gobs_x * bh * 512 + (xb // 64) * bh * 512 + (gob_y % bh) * 512
            + ((xb % 64) // 32) * 256 + ((ys % 8) // 2) * 64 + ((xb % 32) // 16) * 32 + (ys % 2) * 16 + (xb % 16))
    out = np.zeros(size, np.uint8)
    lin = np.frombuffer(linear, np.uint8).reshape(h_el, w_el, bpe)
    for k in range(bpe):
        out[addr + k] = lin[..., k]
    return out.tobytes()
