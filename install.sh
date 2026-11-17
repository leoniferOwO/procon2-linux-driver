#!/bin/sh
# Installs the Switch 2 Pro Controller -> Xbox 360 driver for the current user.
# Run as your normal user (not with sudo): it asks for sudo only for the udev rule.
set -e
cd "$(dirname "$0")"

if [ "$(id -u)" -eq 0 ]; then
    echo "Run as your normal user, not root/sudo." >&2; exit 1
fi
python3 -c "import evdev" 2>/dev/null || {
    echo "Missing python-evdev (Arch: python-evdev, Debian/Ubuntu: python3-evdev, Fedora: python3-evdev)." >&2; exit 1; }
python3 -c "import ctypes; ctypes.CDLL('libusb-1.0.so.0')" 2>/dev/null || {
    echo "Missing libusb-1.0 (Arch: libusb, Debian/Ubuntu: libusb-1.0-0, Fedora: libusb1)." >&2; exit 1; }

install -Dm755 procon2_xbox.py "$HOME/.local/bin/procon2_xbox.py"
install -Dm644 procon2-xbox.service "$HOME/.config/systemd/user/procon2-xbox.service"
systemctl --user daemon-reload

sudo install -Dm644 99-procon2-xbox.rules /etc/udev/rules.d/99-procon2-xbox.rules
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=misc --sysname-match=uinput
sudo udevadm trigger --action=add --subsystem-match=usb --attr-match=idVendor=057e --attr-match=idProduct=2069

echo "Installed. Plug in the controller (or replug it) and it shows up as an Xbox 360 pad."
