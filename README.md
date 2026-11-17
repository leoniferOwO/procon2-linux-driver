# 🎮 procon2-xbox-driver

**Use the Nintendo Switch 2 Pro Controller on Linux as if it were an Xbox 360 controller.**

Nintendo doesn't make the Switch 2 Pro Controller work outside its console. Plugged into a PC over USB, it is
detected, but it sends no input until it receives a proprietary init sequence.
This driver runs in userspace (no kernel modules) and does three things:

1. 🔌 wakes the controller up over USB with the right sequence;
2. 🎯 reads the stick calibration from the controller's own memory;
3. 🕹️ creates a **virtual Xbox 360 controller**, which Steam and games pick up right away.

## ✅ Requirements

- Linux with systemd
- Python 3 + `python-evdev`
- `libusb-1.0`
- **USB cable** connection (Bluetooth is not supported)

| Distro | Packages |
|---|---|
| Arch / CachyOS | `sudo pacman -S python-evdev libusb` |
| Debian / Ubuntu | `sudo apt install python3-evdev libusb-1.0-0` |
| Fedora | `sudo dnf install python3-evdev libusb1` |

## 🚀 Install

```bash
git clone https://github.com/leoniferOwO/procon2-linux-driver.git
cd procon2-linux-driver
./install.sh
```

Run the script as your normal user, without `sudo`: it asks for your password only for the udev rule.
Then plug in (or replug) the controller and you're good to go.

It's already **permanent**: every time you plug the controller in, a udev rule starts the driver. When you unplug it,
the driver exits on its own.

```bash
systemctl --user status procon2-xbox.service   # check that it's running
```

## 🗺️ Button mapping

Buttons are mapped **by position**, like Steam does: the bottom face button is always "A".

| Switch 2 | Xbox 360 |
|---|---|
| B / A / Y / X | A / B / X / Y |
| L / R | LB / RB |
| ZL / ZR | LT / RT (digital) |
| − / + / Home | Back / Start / Guide |
| L3 / R3, D-pad, sticks | same |

Not mapped: GL/GR, C, Capture, rumble and gyro (the Xbox 360 controller has none of these).

## ⚠️ Notes

- If KDE's **System Settings → Game Controller** page is open, it holds the controller and the driver can't start:
  close it.
- To uninstall:
  ```bash
  rm ~/.local/bin/procon2_xbox.py ~/.config/systemd/user/procon2-xbox.service
  sudo rm /etc/udev/rules.d/99-procon2-xbox.rules
  ```

## 🤖 Vibecoded

All the code for the Linux part was **vibecoded with [Claude Code](https://claude.com/claude-code)**: I plugged in the
controller and described the problem, Claude did the rest. It works on my machine, but use it at your own risk.

## 🙏 Credits

The USB protocol (init sequence, calibration reads, report format) comes from
[SDL](https://github.com/libsdl-org/SDL)'s Switch 2 driver (`src/joystick/hidapi/SDL_hidapi_switch2.c`). Thanks to
its developers for the reverse engineering.
