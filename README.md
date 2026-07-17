<div align="center">

# barcode-scan

[![Stars](https://img.shields.io/github/stars/da1loks/barcode-scanner?style=flat&logo=github)](https://github.com/da1loks/barcode-scanner/stargazers)
[![Forks](https://img.shields.io/github/forks/da1loks/barcode-scanner?style=flat&logo=github)](https://github.com/da1loks/barcode-scanner/network/members)
[![License](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Ubuntu%2022.04-lightgrey)](#install)
[![OpenCV](https://img.shields.io/badge/opencv-camera-green?logo=opencv&logoColor=white)](https://opencv.org/)
[![ZXing](https://img.shields.io/badge/decoder-zxing--cpp-orange)](https://github.com/zxing-cpp/zxing-cpp)

Live USB webcam barcode scanner for **Windows** and **Ubuntu 22.04**. Point the camera at a barcode — the decoded value is printed to the console.

</div>

---

## Features

- Reads barcodes from a USB webcam in real time
- Works on Windows (DirectShow) and Linux (V4L2)
- Draws a green outline around detected codes
- Prints each unique scan once to the terminal
- Small resizable preview window
- Camera index selectable from the command line

## Supported formats

EAN-13, EAN-8, UPC-A, UPC-E, Code 128, Code 39, QR, and other formats supported by [zxing-cpp](https://github.com/zxing-cpp/zxing-cpp).

## Stack

| Piece | Role |
| --- | --- |
| **Python 3.10+** | runtime |
| **OpenCV** | webcam capture & preview |
| **zxing-cpp** | barcode decoding |
| **NumPy** | frame helpers |

## Requirements

- Windows 10/11 **or** Ubuntu 22.04
- Python 3.10 or newer
- A USB webcam (or any OpenCV-visible camera)

## Install

### Windows

```bash
git clone https://github.com/da1loks/barcode-scanner.git
cd barcode-scanner
pip install -r requirements.txt
```

### Ubuntu 22.04

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv \
  libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
  libgtk-3-0 v4l-utils

sudo usermod -aG video $USER
```

Log out and back in (or reboot) so the `video` group applies, then:

```bash
git clone https://github.com/da1loks/barcode-scanner.git
cd barcode-scanner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

List cameras if needed:

```bash
v4l2-ctl --list-devices
```

## Usage

```bash
python scan.py
```

On Ubuntu:

```bash
python3 scan.py
```

By default the script opens camera index `1` (often the USB cam; `0` is usually the built-in laptop camera). On a machine with only one USB camera, try `0`.

Pick another camera:

```bash
python scan.py 0
python scan.py 2
```

| Key | Action |
| --- | --- |
| `q` | quit |

When a barcode is recognized, its value is printed in the same terminal where the script is running.

### Quick test

A valid sample barcode is included:

```text
test_code.png
```

Open it on screen (or print it), run the scanner, and point the camera at it. You should see `1234567890` in the console.

> Tip: decorative “barcode-looking” images from the internet often are not real encodings and will not scan. Use a real product label or `test_code.png`.

## Project layout

```text
barcode-scanner/
├── scan.py            # main scanner
├── requirements.txt   # dependencies
├── test_code.png      # sample Code 128 barcode
└── README.md
```

## License

MIT
