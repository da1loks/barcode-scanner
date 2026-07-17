import sys
import platform
import cv2
import numpy as np
import zxingcpp

cam = int(sys.argv[1]) if len(sys.argv) > 1 else 1

if platform.system() == "Windows":
    backends = [cv2.CAP_DSHOW, cv2.CAP_ANY]
else:
    backends = [cv2.CAP_V4L2, cv2.CAP_ANY]

cap = None
for backend in backends:
    cap = cv2.VideoCapture(cam, backend)
    if cap.isOpened():
        break
    cap.release()
    cap = None

if cap is None or not cap.isOpened():
    print(f"камера {cam} не открылась, попробуй другой номер")
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

print(f"камера {cam} ({platform.system()})")
cv2.namedWindow("scan", cv2.WINDOW_NORMAL)
cv2.resizeWindow("scan", 480, 270)

last = None


def decode(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    imgs = [
        frame,
        gray,
        cv2.createCLAHE(2.0, (8, 8)).apply(gray),
        cv2.resize(gray, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC),
    ]
    for img in imgs:
        found = zxingcpp.read_barcodes(img)
        if found:
            return found
    return []


while True:
    ok, frame = cap.read()
    if not ok:
        break

    for r in decode(frame):
        data = r.text
        if not data:
            continue
        pos = r.position
        pts = np.array([
            [pos.top_left.x, pos.top_left.y],
            [pos.top_right.x, pos.top_right.y],
            [pos.bottom_right.x, pos.bottom_right.y],
            [pos.bottom_left.x, pos.bottom_left.y],
        ], np.int32)
        cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
        cv2.putText(frame, data, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        if data != last:
            print(data)
            last = data

    cv2.imshow("scan", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
