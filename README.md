<div align="center">

# barcode-scan

[![Stars](https://img.shields.io/github/stars/da1loks/barcode-scanner?style=flat&logo=github)](https://github.com/da1loks/barcode-scanner/stargazers)
[![Forks](https://img.shields.io/github/forks/da1loks/barcode-scanner?style=flat&logo=github)](https://github.com/da1loks/barcode-scanner/network/members)
[![License](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Ubuntu%2022.04-lightgrey)](#install)
[![OpenCV](https://img.shields.io/badge/opencv-camera-green?logo=opencv&logoColor=white)](https://opencv.org/)
[![ZXing](https://img.shields.io/badge/decoder-zxing--cpp-orange)](https://github.com/zxing-cpp/zxing-cpp)

Live USB webcam barcode scanner for **Windows** and **Ubuntu 22.04**. Manipulators call the backend (pull model): create a find-task, get coordinates over WebSocket or HTTP, then ACK.

</div>

---

# English

## How the program works

There are two ways to run the project:

| Mode | Command | What it does |
| --- | --- | --- |
| Simple | `python scan.py` | Opens the camera, decodes barcodes, prints code + coordinates to the console |
| Server | `python server.py` | Same camera loop **plus** an HTTP/WebSocket API for robot manipulators |

### Big picture (server mode)

1. OpenCV grabs frames from the USB webcam.
2. `zxing-cpp` tries to decode barcodes in each frame (with a few image variants for reliability).
3. For every hit you get:
   - pixel coordinates (`center`, `bbox`, `polygon`)
   - normalized coordinates (`0…1` relative to frame size)
   - optional robot coordinates in mm (after calibration)
4. Manipulators **know the backend URL**. They create tasks, wait for results, and ACK. The backend **never** calls robot IPs or webhooks.

```text
  USB camera ──► OpenCV frame ──► zxing decode ──► match tasks by code + priority
                                                      │
                         ┌────────────────────────────┼────────────────────────────┐
                         ▼                            ▼                            ▼
                   console print              WebSocket push                 SQLite history
                   + preview window           / HTTP poll                    history.db
```

### Task lifecycle

```text
manipulator                         barcode-scanner
    |                                      |
    |  WS /ws?manipulator_id=arm-1         |
    |=====================================>|  (stays open)
    |  POST /tasks {code, priority, ...}   |
    |------------------------------------->|  status: searching
    |                                      |  camera looks for that code
    |  WS task_update  status=found        |
    |<=====================================|  result has coordinates
    |  POST /tasks/{id}/ack                |
    |------------------------------------->|  status: acked
```

Statuses: `searching` → `found` | `timeout` | `cancelled` → `acked`.

### Priority queue

Each task has `priority` (`0…1000`, higher first).

- Several arms ask for **different** codes; several barcodes appear in one frame → high-priority tasks are matched first.
- Several tasks want the **same** code → only the highest-priority task gets `found`; others keep searching.
- Preview shows the current top task: `focus p=… code`.
- `GET /health` returns the live queue order.

### Coordinates

| Field | Meaning |
| --- | --- |
| `center` / `bbox` / `polygon` | pixels in the camera image |
| `normalized` | same values divided by frame width/height (`0…1`) — stable if resolution changes |
| `robot_mm` | mapped into the robot base frame (mm), only if calibration is set |
| `frame` | current image size used for normalization |

### Calibration (pixel → robot mm)

You teach the plane under the camera with **≥ 4** point pairs: each pair is `{pixel, robot_mm}`. The server builds a homography and saves it to `calibration.json`. After that every detection can include `robot_mm`.

### History

Every important event (`created`, `found`, `timeout`, `acked`, `cancelled`) is written to SQLite (`history.db`) with who asked, which code, coordinates, and time. Useful for shift review and debugging — not only “what is in RAM right now”.

### Files

| File | Role |
| --- | --- |
| `scan.py` | simple console scanner |
| `server.py` | camera thread + FastAPI + WebSocket |
| `camera.py` | open camera, decode, draw overlay |
| `coords.py` | normalized coords + calibration |
| `history.py` | SQLite logging / queries |

---

## Features

- Real-time USB webcam barcode reading
- Windows (DirectShow) and Linux (V4L2)
- Console output: code + coordinates
- Green outline on the preview window
- Pull HTTP API — manipulators call the backend
- WebSocket for instant `found` / `detection` events
- Normalized coords + optional pixel→robot_mm calibration
- Task flow: create → (ws or poll) → ack
- Priority queue
- SQLite history
- Resizable preview; camera index from CLI / env

## Supported formats

EAN-13, EAN-8, UPC-A, UPC-E, Code 128, Code 39, QR, and other formats supported by [zxing-cpp](https://github.com/zxing-cpp/zxing-cpp).

## Stack

| Piece | Role |
| --- | --- |
| **Python 3.10+** | runtime |
| **OpenCV** | webcam capture & preview |
| **zxing-cpp** | barcode decoding |
| **FastAPI / Uvicorn** | HTTP + WebSocket API |
| **SQLite** | history |
| **NumPy** | frame / calibration math |

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

## Usage (simple scanner)

```bash
python scan.py
```

On Ubuntu: `python3 scan.py`

Default camera index is `1` (often USB; `0` is often the laptop camera). Override:

```bash
python scan.py 0
python scan.py 2
```

| Key | Action |
| --- | --- |
| `q` | quit |

Example console line:

```text
1234567890  x=640 y=360  nx=0.500 ny=0.500
```

### Quick test

Open `test_code.png` (real Code 128 sample), run the scanner, point the camera at it. You should see `1234567890`.

> Decorative “barcode-looking” images from the internet often are not real encodings and will not scan.

## HTTP API (pull + WebSocket)

Start the API + camera:

```bash
python server.py
```

| Variable | Default | Description |
| --- | --- | --- |
| `CAM_INDEX` | `1` | camera index |
| `HOST` | `0.0.0.0` | bind address |
| `PORT` | `8080` | API port |
| `CALIB_PATH` | `calibration.json` | pixel→robot map |
| `HISTORY_DB` | `history.db` | SQLite history file |

### WebSocket

```text
ws://127.0.0.1:8080/ws?manipulator_id=arm-1
ws://127.0.0.1:8080/ws?task_id=<uuid>
```

| `event` | When |
| --- | --- |
| `hello` | after connect |
| `task_update` | created / found / timeout / acked / cancelled |
| `detection` | any barcode seen |
| `pong` | reply to client `ping` |

### Create a task

```bash
curl -X POST http://127.0.0.1:8080/tasks ^
  -H "Content-Type: application/json" ^
  -d "{\"code\": \"1234567890\", \"manipulator_id\": \"arm-1\", \"timeout_sec\": 60, \"priority\": 10}"
```

Example `result` when found:

```json
{
  "code": "1234567890",
  "center": { "x": 640, "y": 360 },
  "bbox": { "x": 520, "y": 330, "w": 240, "h": 60 },
  "polygon": [[520, 330], [760, 330], [760, 390], [520, 390]],
  "normalized": {
    "center": { "x": 0.5, "y": 0.5 },
    "bbox": { "x": 0.406, "y": 0.458, "w": 0.188, "h": 0.083 }
  },
  "robot_mm": { "x": 210.5, "y": 95.0, "z": 0.0 },
  "calibration_ok": true,
  "frame": { "width": 1280, "height": 720 },
  "ts": 1710000000.0
}
```

ACK:

```bash
curl -X POST http://127.0.0.1:8080/tasks/<task_id>/ack ^
  -H "Content-Type: application/json" ^
  -d "{\"manipulator_id\": \"arm-1\"}"
```

### Calibration

```bash
curl -X PUT http://127.0.0.1:8080/calibration ^
  -H "Content-Type: application/json" ^
  -d "{\"points\":[{\"pixel\":{\"x\":100,\"y\":100},\"robot_mm\":{\"x\":0,\"y\":0}},{\"pixel\":{\"x\":1180,\"y\":100},\"robot_mm\":{\"x\":400,\"y\":0}},{\"pixel\":{\"x\":100,\"y\":620},\"robot_mm\":{\"x\":0,\"y\":300}},{\"pixel\":{\"x\":1180,\"y\":620},\"robot_mm\":{\"x\":400,\"y\":300}}]}"
```

### History

```bash
curl "http://127.0.0.1:8080/history?limit=20"
curl "http://127.0.0.1:8080/history?manipulator_id=arm-1&event=found"
```

### Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | camera + priority queue + ws + calibration |
| `GET` | `/detections/latest` | last barcode seen |
| `GET` | `/history` | SQLite log |
| `WS` | `/ws` | live events |
| `POST` | `/tasks` | start search |
| `GET` | `/tasks` | list tasks |
| `GET` | `/tasks/{id}` | poll one task |
| `POST` | `/tasks/{id}/ack` | confirm coords received |
| `DELETE` | `/tasks/{id}` | cancel while searching |
| `GET/PUT/DELETE` | `/calibration` | pixel→robot_mm map |

Interactive docs: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)

## Docker deploy (Linux host + USB camera)

The API runs **headless** in the container (no preview window). The host USB camera is passed through as `/dev/video*`.

> Camera passthrough works reliably on a **Linux** host. Docker Desktop on Windows/macOS usually cannot expose a USB webcam to Linux containers.

### 1. Find the camera on the host

```bash
v4l2-ctl --list-devices
ls -l /dev/video*
```

Often the USB cam is `/dev/video0` (set `CAM_INDEX=0`). If it is `video1`, edit `devices:` in `docker-compose.yml` and set `CAM_INDEX=1`.

### 2. Build and run

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f
```

API: `http://HOST:8080` — docs at `/docs`.

### 3. Persist data

`history.db` and `calibration.json` live in the Docker volume `scanner-data` (`/data` inside the container).

### 4. Useful commands

```bash
docker compose ps
docker compose restart
docker compose down
curl http://127.0.0.1:8080/health
```

If OpenCV cannot open the camera inside the container, uncomment `privileged: true` in `docker-compose.yml`, confirm the device path, and ensure the container user can access the `video` group.

Env vars in compose / container:

| Variable | Default in Docker | Meaning |
| --- | --- | --- |
| `HEADLESS` | `1` | no OpenCV window |
| `CAM_INDEX` | `0` | V4L2 camera index |
| `HISTORY_DB` | `/data/history.db` | SQLite path |
| `CALIB_PATH` | `/data/calibration.json` | calibration file |

## Project layout

```text
barcode-scanner/
├── scan.py
├── server.py
├── camera.py
├── coords.py
├── history.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── test_code.png
└── README.md
```

## License

MIT

---

# Русский

## Как работает программа

Запускать можно двумя способами:

| Режим | Команда | Что делает |
| --- | --- | --- |
| Простой | `python scan.py` | Открывает камеру, читает штрихкоды, пишет код и координаты в консоль |
| Сервер | `python server.py` | Тот же цикл камеры **плюс** HTTP/WebSocket API для манипуляторов |

### Общая схема (режим сервера)

1. OpenCV берёт кадры с USB-камеры.
2. `zxing-cpp` пытается распознать штрихкоды на кадре (несколько вариантов картинки для надёжности).
3. На каждое попадание вы получаете:
   - координаты в пикселях (`center`, `bbox`, `polygon`)
   - нормализованные координаты (`0…1` от размера кадра)
   - при желании — координаты в мм в базе робота (после калибровки)
4. Манипуляторы **знают URL бэкенда**. Они создают задачи, ждут результат и делают ACK. Бэкенд **никогда** сам не ходит на IP роботов и не шлёт им webhook’и.

```text
  USB-камера ──► кадр OpenCV ──► zxing ──► сопоставление задач по коду + приоритету
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    ▼                          ▼                          ▼
              вывод в консоль           push по WebSocket            история SQLite
              + окно превью              / опрос HTTP                 history.db
```

### Жизненный цикл задачи

```text
манипулятор                         barcode-scanner
    |                                      |
    |  WS /ws?manipulator_id=arm-1         |
    |=====================================>|  (сокет остаётся открытым)
    |  POST /tasks {code, priority, ...}   |
    |------------------------------------->|  статус: searching
    |                                      |  камера ищет этот код
    |  WS task_update  status=found        |
    |<=====================================|  в result — координаты
    |  POST /tasks/{id}/ack                |
    |------------------------------------->|  статус: acked
```

Статусы: `searching` → `found` | `timeout` | `cancelled` → `acked`.

### Очередь с приоритетами

У каждой задачи есть `priority` (`0…1000`, больше = важнее).

- Несколько рук просят **разные** коды, в кадре видно несколько штрихкодов → сначала закрываются задачи с высоким приоритетом.
- Несколько задач хотят **один и тот же** код → `found` получает только самая приоритетная, остальные продолжают ждать.
- В превью показывается текущий фокус: `focus p=… code`.
- `GET /health` отдаёт живую очередь.

### Координаты

| Поле | Смысл |
| --- | --- |
| `center` / `bbox` / `polygon` | пиксели на изображении с камеры |
| `normalized` | те же значения / ширину и высоту кадра (`0…1`) — удобно, если разрешение меняется |
| `robot_mm` | пересчёт в систему робота (мм), только после калибровки |
| `frame` | размер кадра, по которому считалась нормализация |

### Калибровка (пиксель → мм робота)

Нужно задать **≥ 4** пары точек на плоскости под камерой: `{pixel, robot_mm}`. Сервер строит гомографию и сохраняет её в `calibration.json`. После этого в ответах может появляться `robot_mm`.

### История

Важные события (`created`, `found`, `timeout`, `acked`, `cancelled`) пишутся в SQLite (`history.db`): кто просил, какой код, координаты, время. Нужно для разбора смен и отладки, а не только «что сейчас лежит в памяти».

### Файлы

| Файл | Назначение |
| --- | --- |
| `scan.py` | простой сканер в консоль |
| `server.py` | поток камеры + FastAPI + WebSocket |
| `camera.py` | открытие камеры, декод, отрисовка |
| `coords.py` | нормализация + калибровка |
| `history.py` | запись и чтение SQLite |

---

## Возможности

- Чтение штрихкодов с USB-камеры в реальном времени
- Windows (DirectShow) и Linux (V4L2)
- Вывод в консоль: код + координаты
- Зелёная обводка на превью
- Pull HTTP API — манипуляторы ходят на бэкенд
- WebSocket для мгновенных событий `found` / `detection`
- Нормализованные координаты + опциональная калибровка в мм робота
- Сценарий задачи: создать → (ws или poll) → ack
- Очередь с приоритетами
- История в SQLite
- Масштабируемое превью; индекс камеры из CLI / env

## Поддерживаемые форматы

EAN-13, EAN-8, UPC-A, UPC-E, Code 128, Code 39, QR и другие форматы [zxing-cpp](https://github.com/zxing-cpp/zxing-cpp).

## Стек

| Часть | Роль |
| --- | --- |
| **Python 3.10+** | среда выполнения |
| **OpenCV** | захват камеры и превью |
| **zxing-cpp** | распознавание штрихкодов |
| **FastAPI / Uvicorn** | HTTP + WebSocket API |
| **SQLite** | история |
| **NumPy** | кадры / математика калибровки |

## Требования

- Windows 10/11 **или** Ubuntu 22.04
- Python 3.10 или новее
- USB-веб-камера (или любая камера, видимая OpenCV)

## Установка

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

Выйдите из сессии и зайдите снова (или перезагрузитесь), чтобы применилась группа `video`, затем:

```bash
git clone https://github.com/da1loks/barcode-scanner.git
cd barcode-scanner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Список камер при необходимости:

```bash
v4l2-ctl --list-devices
```

## Использование (простой сканер)

```bash
python scan.py
```

На Ubuntu: `python3 scan.py`

По умолчанию индекс камеры `1` (часто USB; `0` — обычно встроенная). Можно указать другой:

```bash
python scan.py 0
python scan.py 2
```

| Клавиша | Действие |
| --- | --- |
| `q` | выход |

Пример строки в консоли:

```text
1234567890  x=640 y=360  nx=0.500 ny=0.500
```

### Быстрый тест

Откройте `test_code.png` (настоящий Code 128), запустите сканер, наведите камеру. В консоли должно появиться `1234567890`.

> Картинки «похожие на штрихкод» из интернета часто не являются настоящим кодом и не сканируются.

## HTTP API (pull + WebSocket)

Запуск API + камеры:

```bash
python server.py
```

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `CAM_INDEX` | `1` | индекс камеры |
| `HOST` | `0.0.0.0` | адрес прослушивания |
| `PORT` | `8080` | порт API |
| `CALIB_PATH` | `calibration.json` | карта пиксель→робот |
| `HISTORY_DB` | `history.db` | файл истории SQLite |

### WebSocket

```text
ws://127.0.0.1:8080/ws?manipulator_id=arm-1
ws://127.0.0.1:8080/ws?task_id=<uuid>
```

| `event` | Когда |
| --- | --- |
| `hello` | после подключения |
| `task_update` | created / found / timeout / acked / cancelled |
| `detection` | любой увиденный штрихкод |
| `pong` | ответ на `ping` клиента |

### Создание задачи

```bash
curl -X POST http://127.0.0.1:8080/tasks ^
  -H "Content-Type: application/json" ^
  -d "{\"code\": \"1234567890\", \"manipulator_id\": \"arm-1\", \"timeout_sec\": 60, \"priority\": 10}"
```

Пример `result` при находке:

```json
{
  "code": "1234567890",
  "center": { "x": 640, "y": 360 },
  "bbox": { "x": 520, "y": 330, "w": 240, "h": 60 },
  "polygon": [[520, 330], [760, 330], [760, 390], [520, 390]],
  "normalized": {
    "center": { "x": 0.5, "y": 0.5 },
    "bbox": { "x": 0.406, "y": 0.458, "w": 0.188, "h": 0.083 }
  },
  "robot_mm": { "x": 210.5, "y": 95.0, "z": 0.0 },
  "calibration_ok": true,
  "frame": { "width": 1280, "height": 720 },
  "ts": 1710000000.0
}
```

Подтверждение:

```bash
curl -X POST http://127.0.0.1:8080/tasks/<task_id>/ack ^
  -H "Content-Type: application/json" ^
  -d "{\"manipulator_id\": \"arm-1\"}"
```

### Калибровка

```bash
curl -X PUT http://127.0.0.1:8080/calibration ^
  -H "Content-Type: application/json" ^
  -d "{\"points\":[{\"pixel\":{\"x\":100,\"y\":100},\"robot_mm\":{\"x\":0,\"y\":0}},{\"pixel\":{\"x\":1180,\"y\":100},\"robot_mm\":{\"x\":400,\"y\":0}},{\"pixel\":{\"x\":100,\"y\":620},\"robot_mm\":{\"x\":0,\"y\":300}},{\"pixel\":{\"x\":1180,\"y\":620},\"robot_mm\":{\"x\":400,\"y\":300}}]}"
```

### История

```bash
curl "http://127.0.0.1:8080/history?limit=20"
curl "http://127.0.0.1:8080/history?manipulator_id=arm-1&event=found"
```

### Эндпоинты

| Метод | Путь | Описание |
| --- | --- | --- |
| `GET` | `/health` | камера + очередь + ws + калибровка |
| `GET` | `/detections/latest` | последний увиденный штрихкод |
| `GET` | `/history` | лог SQLite |
| `WS` | `/ws` | живые события |
| `POST` | `/tasks` | начать поиск |
| `GET` | `/tasks` | список задач |
| `GET` | `/tasks/{id}` | опрос одной задачи |
| `POST` | `/tasks/{id}/ack` | подтвердить получение координат |
| `DELETE` | `/tasks/{id}` | отменить поиск |
| `GET/PUT/DELETE` | `/calibration` | карта пиксель→мм робота |

Интерактивная документация: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)

## Деплой в Docker (Linux-хост + USB-камера)

В контейнере API работает в режиме **headless** (без окна превью). USB-камера хоста пробрасывается как `/dev/video*`.

> Проброс камеры стабильно работает на **Linux**-хосте. Docker Desktop на Windows/macOS обычно **не** отдаёт USB-веб-камеру в Linux-контейнер.

### 1. Найти камеру на хосте

```bash
v4l2-ctl --list-devices
ls -l /dev/video*
```

Часто USB-камера — это `/dev/video0` (`CAM_INDEX=0`). Если `video1` — поправь `devices:` в `docker-compose.yml` и выставь `CAM_INDEX=1`.

### 2. Сборка и запуск

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f
```

API: `http://HOST:8080`, документация — `/docs`.

### 3. Данные

`history.db` и `calibration.json` хранятся в Docker volume `scanner-data` (внутри контейнера — `/data`).

### 4. Полезные команды

```bash
docker compose ps
docker compose restart
docker compose down
curl http://127.0.0.1:8080/health
```

Если камера внутри контейнера не открывается — раскомментируй `privileged: true` в `docker-compose.yml`, проверь путь устройства и доступ группы `video`.

| Переменная | В Docker по умолчанию | Смысл |
| --- | --- | --- |
| `HEADLESS` | `1` | без окна OpenCV |
| `CAM_INDEX` | `0` | индекс V4L2-камеры |
| `HISTORY_DB` | `/data/history.db` | путь к SQLite |
| `CALIB_PATH` | `/data/calibration.json` | файл калибровки |

## Структура проекта

```text
barcode-scanner/
├── scan.py
├── server.py
├── camera.py
├── coords.py
├── history.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── test_code.png
└── README.md
```

## Лицензия

MIT
