import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import base64
import os
import time

# ==========================================
# 🎮 实验控制台
# ==========================================
SIMULATE_DELAY = 0
# ==========================================

app = FastAPI()

# 1. 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- 识别模型初始化 ---
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)
mp_drawing = mp.solutions.drawing_utils


def count_fingers(hand_landmarks, handedness):
    landmarks = hand_landmarks.landmark
    fingers = []
    tip_ids = [4, 8, 12, 16, 20]
    pip_ids = [3, 6, 10, 14, 18]
    label = handedness.classification[0].label

    if label == "Right":
        if landmarks[tip_ids[0]].x < landmarks[tip_ids[0] - 1].x:
            fingers.append(1)
        else:
            fingers.append(0)
    else:
        if landmarks[tip_ids[0]].x > landmarks[tip_ids[0] - 1].x:
            fingers.append(1)
        else:
            fingers.append(0)

    for i in range(1, 5):
        if landmarks[tip_ids[i]].y < landmarks[pip_ids[i]].y:
            fingers.append(1)
        else:
            fingers.append(0)
    return str(fingers.count(1))


# ============================================================
# 🌟 核心修复：API 接口定义必须放在 StaticFiles 挂载之前！！！
# ============================================================

@app.post("/recognize")  # <--- 先定义这个，服务器就会先匹配这个
async def recognize(file: UploadFile = File(...)):
    if SIMULATE_DELAY > 0:
        time.sleep(SIMULATE_DELAY)

    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None: return {"error": "Image decode failed"}

        image = cv2.flip(image, 1)
        h, w, _ = image.shape
        dynamic_radius = max(1, int(w / 160))
        dynamic_thick = max(1, int(w / 200))

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = hands.process(image_rgb)

        hands_data = []
        if results.multi_hand_landmarks:
            for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                handedness = results.multi_handedness[i]
                digit = count_fingers(hand_landmarks, handedness)
                label = handedness.classification[0].label
                hands_data.append({"label": label, "digit": digit})

                mp_drawing.draw_landmarks(
                    image, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(255, 0, 0), thickness=dynamic_thick, circle_radius=dynamic_radius),
                    mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=dynamic_thick)
                )

        _, buffer = cv2.imencode('.png', image)
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')

        return {
            "imageData": f"data:image/png;base64,{jpg_as_text}",
            "handData": hands_data
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


# ============================================================
# 🌟 核心修复：挂载网页必须放在最后！！！作为“兜底”选项
# ============================================================
base_dir = os.path.dirname(os.path.abspath(__file__))
front_end_dir = os.path.join(base_dir, "front end")

if os.path.exists(front_end_dir):
    print(f"✅ 成功定位前端文件夹：{front_end_dir}")
    # html=True 表示如果访问 / 就自动找 index.html
    app.mount("/", StaticFiles(directory=front_end_dir, html=True), name="static")
else:
    print(f"❌ 错误：找不到文件夹 {front_end_dir}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)