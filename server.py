import asyncio
import os
import sys
import threading
import time
import uuid
from typing import Optional

import cv2
import uvicorn
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from camera import barcode_info, decode, draw_barcode, open_camera
from coords import (
    calibration_status,
    clear_calibration,
    enrich,
    load_calibration,
    set_calibration_points,
)
from history import init_db, log_event, query_history

CAM_INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("CAM_INDEX", "1"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
HISTORY_DB = os.getenv("HISTORY_DB", "history.db")
HEADLESS = os.getenv("HEADLESS", "0").strip().lower() in ("1", "true", "yes", "on")

app = FastAPI(
    title="barcode-scanner",
    description="Pull API + WebSocket for manipulators. Backend never calls robots.",
)
lock = threading.Lock()
tasks: dict[str, dict] = {}
last_hit: Optional[dict] = None
frame_size = {"width": 0, "height": 0}
last_print = None
running = True
loop: Optional[asyncio.AbstractEventLoop] = None
ws_clients: list[dict] = []


class CreateTaskBody(BaseModel):
    code: str = Field(..., min_length=1)
    manipulator_id: Optional[str] = None
    timeout_sec: float = Field(60, ge=1, le=600)
    priority: int = Field(
        0,
        ge=0,
        le=1000,
        description="Higher number is served first when several tasks compete",
    )


class AckBody(BaseModel):
    manipulator_id: Optional[str] = None


class CalibPoint(BaseModel):
    pixel: dict
    robot_mm: dict


class CalibrationBody(BaseModel):
    points: list[CalibPoint] = Field(..., min_length=4)


def public_task(task: dict) -> dict:
    return {
        "task_id": task["task_id"],
        "code": task["code"],
        "manipulator_id": task["manipulator_id"],
        "priority": task["priority"],
        "status": task["status"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
        "timeout_sec": task["timeout_sec"],
        "result": task["result"],
        "frame": task.get("frame") or frame_size,
    }


def task_sort_key(task: dict):
    return (-int(task.get("priority", 0)), float(task.get("created_at", 0)))


def searching_tasks_sorted() -> list[dict]:
    items = [t for t in tasks.values() if t["status"] == "searching"]
    items.sort(key=task_sort_key)
    return items


def expire_tasks(now: float) -> list[dict]:
    changed = []
    for task in tasks.values():
        if task["status"] != "searching":
            continue
        if now - task["created_at"] >= task["timeout_sec"]:
            task["status"] = "timeout"
            task["updated_at"] = now
            changed.append(dict(task))
    return changed


def notify(event: dict):
    if loop is None:
        return
    asyncio.run_coroutine_threadsafe(broadcast(event), loop)


async def broadcast(event: dict):
    dead = []
    for client in list(ws_clients):
        mid = client.get("manipulator_id")
        tid = client.get("task_id")
        task = event.get("task") or {}
        if mid and task.get("manipulator_id") and task.get("manipulator_id") != mid:
            continue
        if tid and task.get("task_id") and task.get("task_id") != tid:
            continue
        ws: WebSocket = client["ws"]
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(client)
    for client in dead:
        if client in ws_clients:
            ws_clients.remove(client)


def build_result(info: dict) -> dict:
    return {
        "code": info["code"],
        "bbox": info["bbox"],
        "center": info["center"],
        "polygon": info["polygon"],
        "normalized": info["normalized"],
        "robot_mm": info["robot_mm"],
        "calibration_ok": info["calibration_ok"],
        "frame": info["frame"],
        "ts": info["ts"],
    }


def camera_loop():
    global last_hit, last_print, frame_size

    cap = open_camera(CAM_INDEX)
    if cap is None:
        print(f"камера {CAM_INDEX} не открылась")
        return

    print(f"камера {CAM_INDEX}")
    print(f"api http://{HOST}:{PORT}")
    print(f"ws   ws://{HOST}:{PORT}/ws")
    print(f"history {HISTORY_DB}")
    print(f"headless={HEADLESS}")
    print("модель: манипуляторы → бэкенд (pull + websocket)")

    if not HEADLESS:
        cv2.namedWindow("scan", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("scan", 480, 270)

    while running:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue

        h, w = frame.shape[:2]
        frame_size = {"width": w, "height": h}
        now = time.time()

        with lock:
            timed_out = expire_tasks(now)
            focus = searching_tasks_sorted()[:1]
        for task in timed_out:
            log_event("timeout", task=task)
            notify({"event": "task_update", "task": public_task(task)})

        if focus:
            t0 = focus[0]
            cv2.putText(
                frame,
                f"focus p={t0['priority']} {t0['code']}",
                (20, frame.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 200, 255),
                2,
            )

        detections = []
        for r in decode(frame):
            if not r.text:
                continue
            info = barcode_info(r)
            info["frame"] = {"width": w, "height": h}
            info["ts"] = now
            enrich(info, w, h)
            draw_barcode(frame, info)
            detections.append(info)

            key = (info["code"], info["center"]["x"] // 5, info["center"]["y"] // 5)
            if key != last_print:
                c = info["center"]
                n = info["normalized"]["center"]
                extra = ""
                if info["robot_mm"]:
                    rm = info["robot_mm"]
                    extra = f"  robot_mm=({rm['x']:.1f},{rm['y']:.1f})"
                print(
                    f"{info['code']}  x={c['x']} y={c['y']}  "
                    f"nx={n['x']:.3f} ny={n['y']:.3f}{extra}"
                )
                last_print = key
                notify({"event": "detection", "detection": info})

        if detections:
            with lock:
                last_hit = detections[0]
                searching = searching_tasks_sorted()
                matches = []
                claimed = set()
                for info in detections:
                    for task in searching:
                        if task["task_id"] in claimed:
                            continue
                        if task["status"] != "searching":
                            continue
                        if task["code"] != info["code"]:
                            continue
                        matches.append((task, info))
                        claimed.add(task["task_id"])
                        break
                matches.sort(key=lambda pair: task_sort_key(pair[0]))

                found_tasks = []
                for task, info in matches:
                    task["status"] = "found"
                    task["result"] = build_result(info)
                    task["frame"] = info["frame"]
                    task["updated_at"] = now
                    found_tasks.append(dict(task))
                    print(
                        f"task {task['task_id']} p={task['priority']} "
                        f"found {info['code']} for {task['manipulator_id']}"
                    )

            for task in found_tasks:
                log_event("found", task=task)
                notify({"event": "task_update", "task": public_task(task)})

        if HEADLESS:
            time.sleep(0.01)
        else:
            cv2.imshow("scan", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if not HEADLESS:
        cv2.destroyAllWindows()


@app.on_event("startup")
async def on_startup():
    global loop
    loop = asyncio.get_running_loop()
    init_db(HISTORY_DB)
    status = load_calibration()
    print(f"calibration ok={status.get('ok')}")
    print(f"history db={HISTORY_DB}")


@app.get("/health")
def health():
    with lock:
        searching = searching_tasks_sorted()
        return {
            "ok": True,
            "camera": CAM_INDEX,
            "frame": frame_size,
            "tasks_searching": len(searching),
            "tasks_total": len(tasks),
            "queue": [
                {
                    "task_id": t["task_id"],
                    "code": t["code"],
                    "priority": t["priority"],
                    "manipulator_id": t["manipulator_id"],
                }
                for t in searching
            ],
            "ws_clients": len(ws_clients),
            "calibration": calibration_status(),
            "history_db": HISTORY_DB,
        }


@app.get("/detections/latest")
def detections_latest():
    with lock:
        if last_hit is None:
            raise HTTPException(404, "nothing scanned yet")
        return last_hit


@app.get("/history")
def history(
    limit: int = Query(50, ge=1, le=500),
    manipulator_id: Optional[str] = None,
    code: Optional[str] = None,
    event: Optional[str] = None,
):
    return query_history(
        limit=limit,
        manipulator_id=manipulator_id,
        code=code,
        event=event,
    )


@app.get("/calibration")
def get_calibration():
    return calibration_status()


@app.put("/calibration")
def put_calibration(body: CalibrationBody):
    try:
        points = [p.model_dump() for p in body.points]
        return set_calibration_points(points)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/calibration")
def delete_calibration():
    return clear_calibration()


@app.post("/tasks")
def create_task(body: CreateTaskBody):
    now = time.time()
    task_id = str(uuid.uuid4())
    task = {
        "task_id": task_id,
        "code": body.code.strip(),
        "manipulator_id": body.manipulator_id,
        "priority": int(body.priority),
        "status": "searching",
        "created_at": now,
        "updated_at": now,
        "timeout_sec": body.timeout_sec,
        "result": None,
        "frame": dict(frame_size),
    }
    with lock:
        expire_tasks(now)
        tasks[task_id] = task
        place = [t["task_id"] for t in searching_tasks_sorted()].index(task_id) + 1
    print(
        f"task {task_id} p={task['priority']} searching {task['code']} "
        f"from {task['manipulator_id']} (queue #{place})"
    )
    log_event("created", task=task)
    out = public_task(task)
    notify({"event": "task_update", "task": out})
    return out


@app.get("/tasks")
def list_tasks(
    status: Optional[str] = Query(None),
    manipulator_id: Optional[str] = Query(None),
):
    with lock:
        expire_tasks(time.time())
        items = list(tasks.values())
    if status:
        items = [t for t in items if t["status"] == status]
    if manipulator_id:
        items = [t for t in items if t["manipulator_id"] == manipulator_id]
    items.sort(
        key=lambda t: (
            0 if t["status"] == "searching" else 1,
            -int(t.get("priority", 0)),
            float(t.get("created_at", 0)),
        )
    )
    return [public_task(t) for t in items]


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    with lock:
        expire_tasks(time.time())
        task = tasks.get(task_id)
        if task is None:
            raise HTTPException(404, "task not found")
        return public_task(task)


@app.post("/tasks/{task_id}/ack")
def ack_task(task_id: str, body: AckBody = AckBody()):
    with lock:
        task = tasks.get(task_id)
        if task is None:
            raise HTTPException(404, "task not found")
        if task["status"] != "found":
            raise HTTPException(409, f"task status is {task['status']}, expected found")
        task["status"] = "acked"
        task["updated_at"] = time.time()
        if body.manipulator_id:
            task["manipulator_id"] = body.manipulator_id
        out = public_task(task)
        snapshot = dict(task)
    log_event("acked", task=snapshot)
    notify({"event": "task_update", "task": out})
    return out


@app.delete("/tasks/{task_id}")
def cancel_task(task_id: str):
    with lock:
        task = tasks.get(task_id)
        if task is None:
            raise HTTPException(404, "task not found")
        if task["status"] == "searching":
            task["status"] = "cancelled"
            task["updated_at"] = time.time()
        out = public_task(task)
        snapshot = dict(task)
    if snapshot["status"] == "cancelled":
        log_event("cancelled", task=snapshot)
    notify({"event": "task_update", "task": out})
    return out


@app.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    manipulator_id: Optional[str] = None,
    task_id: Optional[str] = None,
):
    await websocket.accept()
    client = {"ws": websocket, "manipulator_id": manipulator_id, "task_id": task_id}
    ws_clients.append(client)
    await websocket.send_json(
        {
            "event": "hello",
            "manipulator_id": manipulator_id,
            "task_id": task_id,
            "calibration": calibration_status(),
            "frame": frame_size,
        }
    )
    try:
        while True:
            msg = await websocket.receive_text()
            if msg.strip().lower() in ("ping", '{"type":"ping"}'):
                await websocket.send_json({"event": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        if client in ws_clients:
            ws_clients.remove(client)


if __name__ == "__main__":
    t = threading.Thread(target=camera_loop, daemon=True)
    t.start()
    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    finally:
        running = False
