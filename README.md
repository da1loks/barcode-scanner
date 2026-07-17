<div align="center">

# barcode-scan

[![Stars](https://img.shields.io/github/stars/da1loks/barcode-scanner?style=flat&logo=github)](https://github.com/da1loks/barcode-scanner/stargazers)
[![Forks](https://img.shields.io/github/forks/da1loks/barcode-scanner?style=flat&logo=github)](https://github.com/da1loks/barcode-scanner/network/members)
[![License](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Ubuntu%2022.04-lightgrey)](#install)
[![OpenCV](https://img.shields.io/badge/opencv-camera-green?logo=opencv&logoColor=white)](https://opencv.org/)
[![ZXing](https://img.shields.io/badge/decoder-zxing--cpp-orange)](https://github.com/zxing-cpp/zxing-cpp)

Live USB webcam barcode scanner for **Windows** and **Ubuntu 22.04**. Point the camera at a barcode — the decoded value and on-screen coordinates are printed to the console. An HTTP API can search for a specific code and POST coordinates to a webhook.

</div>

---

## Features

- Reads barcodes from a USB webcam in real time
- Works on Windows (DirectShow) and Linux (V4L2)
- Prints code + screen coordinates (`x`, `y`, bbox)
- Draws a green outline around detected codes
- HTTP API: ask for a product code, get coordinates when found
- Optional outbound webhook (`REPORT_URL`) for found results
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
| **FastAPI / Uvicorn** | HTTP API |
| **httpx** | outbound webhook POSTs |
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

When a barcode is recognized, the console prints the value and coordinates, for example:

```text
1234567890  x=640 y=360  bbox={'x': 520, 'y': 330, 'w': 240, 'h': 60}
```

### Quick test

A valid sample barcode is included:

```text
test_code.png
```

Open it on screen (or print it), run the scanner, and point the camera at it. You should see `1234567890` in the console.

> Tip: decorative “barcode-looking” images from the internet often are not real encodings and will not scan. Use a real product label or `test_code.png`.

## HTTP API

Start the API + camera:

```bash
python server.py
```

Optional env vars:

| Variable | Default | Description |
| --- | --- | --- |
| `CAM_INDEX` | `1` | camera index |
| `HOST` | `0.0.0.0` | bind address |
| `PORT` | `8080` | API port |
| `REPORT_URL` | empty | webhook URL that receives JSON when a target code is found |

```bash
set REPORT_URL=http://127.0.0.1:9000/hook
python server.py
```

### Find a specific barcode

Send the product code. The camera keeps looking until it sees that barcode (or times out). Response includes coordinates; the same JSON is POSTed to `REPORT_URL` if set.

```bash
curl -X POST http://127.0.0.1:8080/find ^
  -H "Content-Type: application/json" ^
  -d "{\"code\": \"1234567890\", \"timeout\": 30}"
```

Example response:

```json
{
  "code": "1234567890",
  "bbox": { "x": 520, "y": 330, "w": 240, "h": 60 },
  "center": { "x": 640, "y": 360 },
  "polygon": [[520, 330], [760, 330], [760, 390], [520, 390]]
}
```

### Other endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | service status |
| `GET` | `/last` | last seen barcode + coordinates |
| `POST` | `/find` | look for a code, return coordinates |
| `POST` | `/report-url` | set/change webhook URL at runtime `{"url":"..."}` |

Docs UI: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)

## Project layout

```text
barcode-scanner/
├── scan.py            # simple console scanner
├── server.py          # camera + HTTP API
├── camera.py          # shared capture / decode helpers
├── requirements.txt
├── test_code.png
└── README.md
```

## License

MIT
