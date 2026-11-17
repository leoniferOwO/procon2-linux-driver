from evdev import ecodes as e

from procon2_xbox import parse_cal, parse_report

# report: B(0x01) + ZR(0x20) pressed, dpad up(0x08), sticks at raw 2048 / 2048
r = bytearray(64)
r[0], r[3], r[4] = 0x09, 0x21, 0x08
r[6], r[7], r[8] = 0x00, 0x08, 0x80  # lx=0x800, ly=0x800
r[9], r[10], r[11] = 0xFF, 0xFF, 0xFF  # rx=0xFFF, ry=0xFFF
s = parse_report(bytes(r), None, None)
assert s[(e.EV_KEY, e.BTN_SOUTH)] == 1 and s[(e.EV_KEY, e.BTN_EAST)] == 0
assert s[(e.EV_ABS, e.ABS_RZ)] == 255 and s[(e.EV_ABS, e.ABS_Z)] == 0
assert s[(e.EV_ABS, e.ABS_HAT0Y)] == -1 and s[(e.EV_ABS, e.ABS_HAT0X)] == 0
assert abs(s[(e.EV_ABS, e.ABS_X)]) < 64 and abs(s[(e.EV_ABS, e.ABS_Y)]) < 64
assert s[(e.EV_ABS, e.ABS_RX)] > 32000 and s[(e.EV_ABS, e.ABS_RY)] < -32000  # Y inverted

# calibrated: neutral 2000, range +/-1500 -> raw 3500 = full right
cal = ((2000, 1500, 1500), (2000, 1500, 1500))
r[6], r[7], r[8] = 0xAC, 0x0D, 0x7D  # lx=0xDAC=3500, ly=0x7D0=2000
s = parse_report(bytes(r), cal, cal)
assert s[(e.EV_ABS, e.ABS_X)] == 32767 and abs(s[(e.EV_ABS, e.ABS_Y)]) <= 1

blk = bytearray(64)
blk[0x28:0x31] = bytes([0xD0, 0x07, 0x7D, 0xDC, 0xC5, 0x5D, 0xDC, 0xC5, 0x5D])
assert parse_cal(bytes(blk), 0x28) == ((2000, 1500, 1500), (2000, 1500, 1500))
assert parse_cal(bytes(blk), 2, user=True) is None  # missing b2a1 magic
print("ok")
