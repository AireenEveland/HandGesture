// --- script.js (Ngrok 修复版) ---

const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const context = canvas.getContext('2d', { willReadFrequently: true });
const processedImage = document.getElementById('processed-image');
const latencyDisplay = document.getElementById('latency-display');
const leftHandDigit = document.getElementById('left-hand-digit');
const rightHandDigit = document.getElementById('right-hand-digit');
const fpsDisplay = document.getElementById('fps-display');

const startButton = document.getElementById('startButton');
const stopButton = document.getElementById('stopButton');
const exportButton = document.getElementById('exportData');
const resetButton = document.getElementById('resetData');
const sessionIdInput = document.getElementById('sessionId');
const networkTypeSelect = document.getElementById('networkType');
const resolutionSelect = document.getElementById('resolutionSelect');

// ✅ 这里的地址已经改对了，配合 Ngrok 使用相对路径
const backendUrl = '/recognize';

let isRecognizing = false;
let dataLogInterval = null;
let videoStream = null;

// 默认参数
let sendWidth = 640;
let sendHeight = 480;

// 数据缓冲区
let performanceData = [];
let frameCount = 0;
let latencyBuffer = [];
let leftBuffer = [];
let rightBuffer = [];

function getDominantValue(arr) {
    if (arr.length === 0) return '-';
    const counts = arr.reduce((acc, val) => { acc[val] = (acc[val] || 0) + 1; return acc; }, {});
    return Object.keys(counts).reduce((a, b) => counts[a] > counts[b] ? a : b);
}

function updateResolutionSettings() {
    const val = resolutionSelect.value;
    const [w, h] = val.split('x').map(Number);
    sendWidth = w;
    sendHeight = h;
    canvas.width = sendWidth;
    canvas.height = sendHeight;
    console.log(`分辨率切换为: ${sendWidth}x${sendHeight}`);
}

// --- 核心发送逻辑 ---
async function sendFrame() {
    if (!isRecognizing || video.readyState < 2) return;

    // 1. 绘制画面
    context.drawImage(video, 0, 0, sendWidth, sendHeight);

    // 2. 使用 PNG 格式
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.7));

    if (!blob) return;
    const formData = new FormData();
    formData.append('file', blob, 'frame.png');

    try {
        const startTime = performance.now();

        // 3. 🌟 关键修改：加入 Ngrok 通行证 Header
        const response = await fetch(backendUrl, {
            method: 'POST',
            body: formData,
            headers: {
                // 这行代码告诉 Ngrok：“我是自己人，别弹警告拦截我！”
                'ngrok-skip-browser-warning': 'true'
            }
        });

        const endTime = performance.now();

        if (response.ok) {
            const latency = Math.round(endTime - startTime);

            latencyDisplay.textContent = `${latency} ms`;
            const result = await response.json();
            processedImage.src = result.imageData;

            const handData = result.handData;
            const lHand = handData.find(h => h.label === 'Left');
            const rHand = handData.find(h => h.label === 'Right');
            const lVal = lHand ? lHand.digit : '-';
            const rVal = rHand ? rHand.digit : '-';

            leftHandDigit.textContent = lVal;
            rightHandDigit.textContent = rVal;

            latencyBuffer.push(latency);
            leftBuffer.push(lVal);
            rightBuffer.push(rVal);
            frameCount++;
        } else {
            console.error("服务器响应错误:", response.status);
        }
    } catch (error) {
        console.error("请求失败:", error);
    }
}

// 递归循环
async function processingLoop() {
    if (!isRecognizing) return;
    await sendFrame();
    if (isRecognizing) requestAnimationFrame(processingLoop);
}

function logAggregatedData() {
    const fps = frameCount;
    const avgLatency = latencyBuffer.length > 0
        ? Math.round(latencyBuffer.reduce((a, b) => a + b, 0) / latencyBuffer.length)
        : 0;

    fpsDisplay.textContent = fps;
    performanceData.push({
        timestamp: new Date().toLocaleTimeString(),
        sessionId: sessionIdInput.value,
        resolution: `${sendWidth}x${sendHeight}`,
        network: networkTypeSelect.value,
        fps: fps,
        avgLatency: avgLatency,
        leftDigit: getDominantValue(leftBuffer),
        rightDigit: getDominantValue(rightBuffer)
    });
    frameCount = 0;
    latencyBuffer = [];
    leftBuffer = [];
    rightBuffer = [];
}

async function startSystem() {
    try {
        videoStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        video.srcObject = videoStream;
        await video.play();

        updateResolutionSettings();
        isRecognizing = true;
        startButton.style.display = 'none';
        stopButton.style.display = 'inline-block';
        resolutionSelect.disabled = false;

        processingLoop();
        dataLogInterval = setInterval(logAggregatedData, 1000);

    } catch (err) {
        alert("摄像头启动失败: " + err.message);
    }
}

function stopSystem() {
    isRecognizing = false;
    if (dataLogInterval) clearInterval(dataLogInterval);
    if (videoStream) videoStream.getTracks().forEach(t => t.stop());
    startButton.style.display = 'inline-block';
    stopButton.style.display = 'none';
}

function exportCSV() {
    if (performanceData.length === 0) { alert("无数据"); return; }
    const header = "Time,Session,Resolution,NetworkLabel,FPS,Latency(ms),Left,Right\n";
    const rows = performanceData.map(d =>
        `${d.timestamp},${d.sessionId},${d.resolution},${d.network},${d.fps},${d.avgLatency},${d.leftDigit},${d.rightDigit}`
    ).join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `final_data_${sessionIdInput.value}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

startButton.addEventListener('click', startSystem);
stopButton.addEventListener('click', stopSystem);
exportButton.addEventListener('click', exportCSV);
resetButton.addEventListener('click', () => { performanceData = []; });
resolutionSelect.addEventListener('change', updateResolutionSettings);


