#!/usr/bin/env python3
"""Userspace driver: USB Switch 2 Pro Controller (057e:2069) -> virtual Xbox 360 pad.

Protocol (init sequence, flash reads, report 0x09 layout) follows SDL's
src/joystick/hidapi/SDL_hidapi_switch2.c. Buttons are mapped by position
(Nintendo B = Xbox A, Nintendo A = Xbox B, ...), like Steam does.
Exits when the controller is missing or unplugged; the systemd unit restarts it.
"""
import ctypes
import sys

import evdev
from evdev import ecodes as e

VID, PID = 0x057E, 0x2069
HID_IFACE, HID_EP_IN = 0, 0x81
CMD_IFACE, CMD_EP_OUT, CMD_EP_IN = 1, 0x02, 0x82

INIT = [
    [0x07, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00],
    [0x0c, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00],
    [0x11, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00],
    [0x0a, 0x91, 0x00, 0x08, 0x00, 0x14, 0x00, 0x00, 0x01, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
     0xff, 0x35, 0x00, 0x46, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    [0x0c, 0x91, 0x00, 0x04, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00],
    [0x01, 0x91, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x00],
    [0x01, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00],
    [0x08, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00],
    [0x03, 0x91, 0x00, 0x0a, 0x00, 0x04, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00],  # report format 0x09 (Pro)
    [0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],  # LED 1
    [0x03, 0x91, 0x00, 0x0d, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff],  # start
]

# (byte, mask, xbox button)
BUTTONS = [
    (3, 0x01, e.BTN_SOUTH), (3, 0x02, e.BTN_EAST), (3, 0x04, e.BTN_NORTH), (3, 0x08, e.BTN_WEST),
    (3, 0x10, e.BTN_TR), (3, 0x40, e.BTN_START), (3, 0x80, e.BTN_THUMBR),
    (4, 0x10, e.BTN_TL), (4, 0x40, e.BTN_SELECT), (4, 0x80, e.BTN_THUMBL),
    (5, 0x01, e.BTN_MODE),
]

usb = ctypes.CDLL("libusb-1.0.so.0")
usb.libusb_open_device_with_vid_pid.restype = ctypes.c_void_p
usb.libusb_open_device_with_vid_pid.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16]
for _f in ("libusb_set_auto_detach_kernel_driver", "libusb_claim_interface", "libusb_release_interface"):
    getattr(usb, _f).argtypes = [ctypes.c_void_p, ctypes.c_int]
for _f in ("libusb_bulk_transfer", "libusb_interrupt_transfer"):
    getattr(usb, _f).argtypes = [ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_char_p, ctypes.c_int,
                                 ctypes.POINTER(ctypes.c_int), ctypes.c_uint]
usb.libusb_close.argtypes = [ctypes.c_void_p]
LIBUSB_ERROR_TIMEOUT = -7


def bulk_cmd(h, cmd, reply_len=64):
    n, buf = ctypes.c_int(), ctypes.create_string_buffer(reply_len)
    if usb.libusb_bulk_transfer(h, CMD_EP_OUT, bytes(cmd), len(cmd), ctypes.byref(n), 1000) != 0:
        raise OSError(f"bulk write failed: {bytes(cmd[:4]).hex()}")
    got = b""
    while len(got) < reply_len:  # replies come in 64-byte chunks
        if usb.libusb_bulk_transfer(h, CMD_EP_IN, buf, 64, ctypes.byref(n), 100) != 0:
            break
        got += buf.raw[:n.value]
        if n.value < 64:
            break
    return got


def read_stick_cal(h, addr):
    """Returns ((x_neutral, x_max, x_min), (y_neutral, y_max, y_min)) or None."""
    cmd = [0x02, 0x91, 0x00, 0x01, 0x00, 0x08, 0x00, 0x00, 0, 0, 0, 0, *addr.to_bytes(4, "little")]
    r = bulk_cmd(h, cmd, 0x50)
    if len(r) < 0x50:
        return None
    return parse_cal(r[0x10:0x50], 0x28 if addr < 0x1FC000 else 2, user=addr >= 0x1FC000)


def parse_cal(block, off, user=False):
    if user and block[0:2] != b"\xb2\xa1":
        return None
    d = block[off:off + 9]
    x = (d[0] | (d[1] & 0xF) << 8, d[3] | (d[4] & 0xF) << 8, d[6] | (d[7] & 0xF) << 8)
    y = (d[1] >> 4 | d[2] << 4, d[4] >> 4 | d[5] << 4, d[7] >> 4 | d[8] << 4)
    return (x, y) if all(x) and all(y) else None


def map_axis(raw, cal, invert):
    if cal:
        neutral, vmax, vmin = cal
        v = raw - neutral
        v = v / vmin if v < 0 else v / vmax
        out = max(-32768, min(32767, int(v * 32767)))
    else:  # shortcut: no calibration -> linear 0..4096, only hit if flash read fails
        out = max(-32768, min(32767, raw * 65535 // 4096 - 32768))
    return ~out if invert else out


def parse_report(d, cal_l, cal_r):
    """d = raw HID report (report id 0x09 at d[0]). Returns {(type, code): value}."""
    s = {(e.EV_KEY, b): int(bool(d[i] & m)) for i, m, b in BUTTONS}
    s[(e.EV_ABS, e.ABS_HAT0X)] = (1 if d[4] & 0x02 else 0) - (1 if d[4] & 0x04 else 0)
    s[(e.EV_ABS, e.ABS_HAT0Y)] = (1 if d[4] & 0x01 else 0) - (1 if d[4] & 0x08 else 0)
    s[(e.EV_ABS, e.ABS_Z)] = 255 if d[4] & 0x20 else 0   # ZL (digital)
    s[(e.EV_ABS, e.ABS_RZ)] = 255 if d[3] & 0x20 else 0  # ZR (digital)
    lx, ly = d[6] | (d[7] & 0xF) << 8, d[7] >> 4 | d[8] << 4
    rx, ry = d[9] | (d[10] & 0xF) << 8, d[10] >> 4 | d[11] << 4
    s[(e.EV_ABS, e.ABS_X)] = map_axis(lx, cal_l and cal_l[0], False)
    s[(e.EV_ABS, e.ABS_Y)] = map_axis(ly, cal_l and cal_l[1], True)
    s[(e.EV_ABS, e.ABS_RX)] = map_axis(rx, cal_r and cal_r[0], False)
    s[(e.EV_ABS, e.ABS_RY)] = map_axis(ry, cal_r and cal_r[1], True)
    return s


def make_xbox_pad():
    stick = evdev.AbsInfo(0, -32768, 32767, 16, 128, 0)
    trig = evdev.AbsInfo(0, 0, 255, 0, 0, 0)
    hat = evdev.AbsInfo(0, -1, 1, 0, 0, 0)
    caps = {
        e.EV_KEY: [b for _, _, b in BUTTONS],
        e.EV_ABS: [(e.ABS_X, stick), (e.ABS_Y, stick), (e.ABS_RX, stick), (e.ABS_RY, stick),
                   (e.ABS_Z, trig), (e.ABS_RZ, trig), (e.ABS_HAT0X, hat), (e.ABS_HAT0Y, hat)],
    }
    # Xbox 360 VID/PID so Steam, SDL and xpad-style mappings recognise it
    return evdev.UInput(caps, name="Microsoft X-Box 360 pad", vendor=0x045E, product=0x028E,
                        version=0x110, bustype=e.BUS_USB)


def main():
    ctx = ctypes.c_void_p()
    if usb.libusb_init(ctypes.byref(ctx)) != 0:
        sys.exit("libusb_init failed")
    h = usb.libusb_open_device_with_vid_pid(ctx, VID, PID)
    if not h:
        sys.exit("Switch 2 Pro Controller not found (or no permission on /dev/bus/usb)")
    try:
        usb.libusb_set_auto_detach_kernel_driver(h, 1)
        for iface in (HID_IFACE, CMD_IFACE):
            if usb.libusb_claim_interface(h, iface) != 0:
                sys.exit(f"cannot claim interface {iface}: another program is using the controller "
                         "(close System Settings > Game Controller, Steam may also grab it)")
        cal_l = read_stick_cal(h, 0x1FC040) or read_stick_cal(h, 0x13080)
        cal_r = read_stick_cal(h, 0x1FC080) or read_stick_cal(h, 0x130C0)
        for cmd in INIT:
            bulk_cmd(h, cmd)
        print(f"controller ready (calibration L={cal_l} R={cal_r})", flush=True)

        pad, last = make_xbox_pad(), {}
        n, buf = ctypes.c_int(), ctypes.create_string_buffer(64)
        while True:
            r = usb.libusb_interrupt_transfer(h, HID_EP_IN, buf, 64, ctypes.byref(n), 1000)
            if r == LIBUSB_ERROR_TIMEOUT:
                continue
            if r != 0:
                sys.exit(f"controller disconnected ({r})")
            d = buf.raw[:n.value]
            if n.value < 12 or d[0] != 0x09:
                continue
            state = parse_report(d, cal_l, cal_r)
            changed = False
            for k, v in state.items():
                if last.get(k) != v:
                    pad.write(k[0], k[1], v)
                    changed = True
            if changed:
                pad.syn()
            last = state
    finally:
        for iface in (HID_IFACE, CMD_IFACE):
            usb.libusb_release_interface(h, iface)
        usb.libusb_close(h)


if __name__ == "__main__":
    main()
