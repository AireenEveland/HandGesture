import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import base64
import os

app = FastAPI()

# 1. 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- 模型初始化 ---
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
        if landmarks[tip_ids[0]].x < landmarks[tip_ids[0] - 1].x: fingers.append(1)
        else: fingers.append(0)
    else:
        if landmarks[tip_ids[0]].x > landmarks[tip_ids[0] - 1].x: fingers.append(1)
        else: fingers.append(0)

    for i in range(1, 5):
        if landmarks[tip_ids[i]].y < landmarks[pip_ids[i]].y: fingers.append(1)
        else: fingers.append(0)
    return str(fingers.count(1))

# --- 核心识别接口 (必须放在静态文件挂载之前) ---
@app.post("/recognize")
async def recognize(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None: return {"error": "Decode failed"}

        image = cv2.flip(image, 1)
        h, w, _ = image.shape
        
        # 动态计算绘制参数 (美化)
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
                
                # 绘制蓝色节点，绿色连线
                mp_drawing.draw_landmarks(
                    image, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(255, 0, 0), thickness=dynamic_thick, circle_radius=dynamic_radius),
                    mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=dynamic_thick)
                )

        # 使用 JPEG 压缩 (质量80)，保证极速传输
        _, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        
        return {
            "imageData": f"data:image/jpeg;base64,{jpg_as_text}",
            "handData": hands_data
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}

# --- 挂载当前文件夹 (自动寻找 index.html) ---
# 只要你的 html 在 main.py 旁边，或者在 front end 文件夹里，这里稍微改一下路径即可
# 假设你把所有文件都放在这个新文件夹的根目录下：
current_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/", StaticFiles(directory=current_dir, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002)