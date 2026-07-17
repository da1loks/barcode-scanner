import os
import sys
import threading
from typing import Optional

import cv2
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from camera import barcode_info, decode, draw_barcode, open_camera

CAM_INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("CAM_INDEX", "1"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
REPORT_URL = os.getenv("REPORT_URL", "").strip()

app = FastAPI(title="barcode-scanner")
lock = threading.Lock()
target_code: Optional[str] = None
target_event = threading.Event()
last_hit: Optional[dict] = None
target_hit: Optional[dict] = None
last_print = None
running = True


class FindBody(BaseModel):
    code: str = Field(..., min_length=1)
    timeout: float = Field(30, ge=1, le=300)


class ReportBody(BaseModel):
    url: str = Field(..., min_length=1)


def post_report(payload: dict):
    url = REPORT_URL
    if not url:
        return
    try:
        r = httpx.post(url, json=payload, timeout=5.0)
        print(f"report -> {url} [{r.status_code}]")
    except Exception as e:
        print(f"report failed: {e}")


def camera_loop():
    global last_hit, target_hit, last_print

    cap = open_camera(CAM_INDEX)
    if cap is None:
        print(f"камера {CAM_INDEX} не открылась")
        return

    print(f"камера {CAM_INDEX}")
    print(f"api http://{HOST}:{PORT}")
    if REPORT_URL:
        print(f"report {REPORT_URL}")

    cv2.namedWindow("scan", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("scan", 480, 270)

    while running:
        ok, frame = cap.read()
        if not ok:
            break

        for r in decode(frame):
            if not r.text:
                continue
            info = barcode_info(r)
            draw_barcode(frame, info)

            with lock:
                last_hit = info
                wanted = target_code

            key = (info["code"], info["center"]["x"] // 5, info["center"]["y"] // 5)
            if key != last_print:
                c = info["center"]
                print(f"{info['code']}  x={c['x']} y={c['y']}  bbox={info['bbox']}")
                last_print = key

            if wanted is not None and info["code"] == wanted:
                with lock:
                    target_hit = info
                if not target_event.is_set():
                    target_event.set()

        cv2.imshow("scan", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


@app.get("/health")
def health():
    return {"ok": True, "camera": CAM_INDEX, "report_url": REPORT_URL or None}


@app.get("/last")
def last():
    with lock:
        if last_hit is None:
            raise HTTPException(404, "nothing scanned yet")
        return last_hit


@app.post("/report-url")
def set_report_url(body: ReportBody):
    global REPORT_URL
    REPORT_URL = body.url.strip()
    return {"report_url": REPORT_URL}


@app.post("/find")
def find(body: FindBody):
    global target_code, target_hit

    code = body.code.strip()
    with lock:
        target_code = code
        target_hit = None
    target_event.clear()

    print(f"ищем {code} (timeout {body.timeout}s)")
    ok = target_event.wait(timeout=body.timeout)

    with lock:
        hit = target_hit
        target_code = None

    if not ok or hit is None:
        raise HTTPException(404, f"barcode {code} not found")

    print(f"найдено {hit['code']} center={hit['center']}")
    post_report({"event": "find", **hit})
    return hit


if __name__ == "__main__":
    t = threading.Thread(target=camera_loop, daemon=True)
    t.start()
    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    finally:
        running = False
