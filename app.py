from flask import Flask, request, jsonify, render_template, send_file
import numpy as np
import cv2
import base64
import time
import threading
import os
import random
import json

app = Flask(__name__)

MODEL_PATH = '/home/agent/focusguard/yunet.onnx'
AUDIO_DIR = '/home/agent/focusguard/audio'

# WICHTIG: OpenCV-DNN ist NICHT thread-safe. Ein Detector + Lock serialisiert
# alle Detektionen. Bei ~80ms/Frame und 250ms-Intervall ist das voellig ausreichend.
detector = cv2.FaceDetectorYN.create(
    MODEL_PATH, "", (0, 0),
    score_threshold=0.4,
    nms_threshold=0.3,
    top_k=5000,
)
detect_lock = threading.Lock()

# Detektion laeuft auf max. 640px Breite:
#  - 81ms statt 323ms (keine Request-Stapelung mehr)
#  - Confidence 0.92 statt 0.78 bei 1280px (YuNet mag moderate Groessen)
MAX_DETECT_WIDTH = 640

state_lock = threading.Lock()
state = {
    'monitoring': False,
    'face_detected': True,
    'away_since': None,
    'away_seconds': 0.0,
    'total_alerts': 0,
    'total_away_time': 0.0,
}

THRESHOLDS = {1: 2, 2: 5, 3: 15, 4: 30}  # Default thresholds (Sekunden)
COOLDOWNS = {1: 6000, 2: 5000, 3: 4000, 4: 3000}  # Default cooldowns (ms)

# Rotation-System: speichert aktuelle Index pro Level
ROTATION_FILE = '/home/agent/focusguard/rotation.json'
rotation_lock = threading.Lock()

def load_rotation():
    """Lade Rotation-Index aus JSON."""
    if os.path.exists(ROTATION_FILE):
        try:
            with open(ROTATION_FILE) as f:
                return json.load(f)
        except:
            pass
    return {f'level{i}': 0 for i in range(5)} | {'comeback': 0}

def save_rotation(rotation):
    """Speichere Rotation-Index."""
    with open(ROTATION_FILE, 'w') as f:
            json.dump(rotation, f)

rotation = load_rotation()

debug_dir = '/home/agent/focusguard/debug'
os.makedirs(debug_dir, exist_ok=True)
debug_counter = {'n': 0}
debug_lock = threading.Lock()


def _detect_face(frame):
    """Thread-sichere Detektion. Gibt (face_present, confidence) zurueck."""
    h, w = frame.shape[:2]
    if w > MAX_DETECT_WIDTH:
        scale = MAX_DETECT_WIDTH / w
        frame = cv2.resize(frame, (MAX_DETECT_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = frame.shape[:2]

    try:
        with detect_lock:
            detector.setInputSize((w, h))
            _, faces = detector.detect(frame)
    except Exception as e:
        # Im Fehlerfall NICHT als "abwesend" werten – das erzeugt Falschalarme.
        print(f"[detect] Fehler: {e}")
        return None, 0.0, frame

    if faces is None or len(faces) == 0:
        return False, 0.0, frame
    return True, float(faces[0][-1]), frame


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/detect', methods=['POST'])
def detect():
    if not state['monitoring']:
        return jsonify({'face': True, 'away_seconds': 0, 'alert_level': 0, 'monitoring': False})

    data = (request.json or {}).get('frame', '')
    if not data:
        return jsonify({'error': 'no frame'}), 400
    if ',' in data:
        data = data.split(',')[1]

    try:
        img_bytes = base64.b64decode(data)
        nparr     = np.frombuffer(img_bytes, np.uint8)
        frame     = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        frame = None

    if frame is None:
        # Kaputter Frame: nicht als Abwesenheit zaehlen.
        return jsonify({'face': True, 'confidence': 0.0, 'away_seconds': round(state['away_seconds'], 1),
                        'alert_level': 0, 'monitoring': True,
                        'total_alerts': state['total_alerts'],
                        'total_away_time': round(state['total_away_time'], 0)})

    face_present, confidence, det_frame = _detect_face(frame)

    # Debug-Frame alle 30 Detektionen
    with debug_lock:
        debug_counter['n'] += 1
        if debug_counter['n'] % 30 == 0:
            ts = int(time.time())
            cv2.imwrite(f"{debug_dir}/frame_{ts}.jpg", det_frame)
            with open(f"{debug_dir}/frame_{ts}.txt", "w") as f:
                f.write(f"face={face_present} conf={confidence:.3f} "
                        f"src={frame.shape[1]}x{frame.shape[0]} "
                        f"det={det_frame.shape[1]}x{det_frame.shape[0]} time={ts}\n")

    if face_present is None:
        # Detektionsfehler: Zustand unveraendert lassen.
        return jsonify({'face': True, 'confidence': 0.0,
                        'away_seconds': round(state['away_seconds'], 1),
                        'alert_level': 0, 'monitoring': True,
                        'total_alerts': state['total_alerts'],
                        'total_away_time': round(state['total_away_time'], 0)})

    with state_lock:
        now = time.time()
        state['face_detected'] = face_present
        if face_present:
            if state['away_since'] is not None:
                state['total_away_time'] += now - state['away_since']
            state['away_since']   = None
            state['away_seconds'] = 0.0
        else:
            if state['away_since'] is None:
                state['away_since'] = now
                state['total_alerts'] += 1
            state['away_seconds'] = now - state['away_since']

    away = state['away_seconds']
    if   away < THRESHOLDS[1]: level = 0
    elif away < THRESHOLDS[2]: level = 1
    elif away < THRESHOLDS[3]: level = 2
    elif away < THRESHOLDS[4]: level = 3
    else:                       level = 4

    return jsonify({
        'face':            face_present,
        'confidence':      round(confidence, 3),
        'away_seconds':    round(away, 1),
        'alert_level':     level,
        'monitoring':      True,
        'total_alerts':    state['total_alerts'],
        'total_away_time': round(state['total_away_time'], 0),
    })


@app.route('/control', methods=['POST'])
def control():
    action = (request.json or {}).get('action')
    with state_lock:
        if action == 'start':
            state.update({'monitoring': True, 'away_since': None,
                          'away_seconds': 0.0, 'total_alerts': 0, 'total_away_time': 0.0})
        elif action == 'stop':
            state.update({'monitoring': False, 'away_since': None, 'away_seconds': 0.0})
    return jsonify({'ok': True, 'monitoring': state['monitoring']})


@app.route('/alert/<level_type>', methods=['GET'])
def alert(level_type):
    """Stream rotated alert audio. Rotation: Alle Sprüche einmal, dann wieder von vorne."""
    global rotation
    
    # Level-Type validieren
    if level_type == 'comeback':
        key = 'comeback'
        prefix = 'comeback_'
    elif level_type.isdigit() and 0 <= int(level_type) < 5:
        key = f'level{level_type}'
        prefix = f'level{level_type}_'
    else:
        return jsonify({'error': 'invalid level'}), 400
    
    # Lade alle Audio-Dateien für dieses Level
    audio_files = sorted([f for f in os.listdir(AUDIO_DIR) if f.startswith(prefix)])
    if not audio_files:
        return jsonify({'error': f'no audio files for {key}'}), 404
    
    # Rotation: nächster Index
    with rotation_lock:
        idx = rotation.get(key, 0) % len(audio_files)
        audio_file = audio_files[idx]
        rotation[key] = (idx + 1) % len(audio_files)
        save_rotation(rotation)
    
    audio_path = os.path.join(AUDIO_DIR, audio_file)
    return send_file(audio_path, mimetype='audio/mpeg', as_attachment=False)


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """GET: Aktuelle Thresholds & Cooldowns. POST: Update."""
    global THRESHOLDS, COOLDOWNS
    
    if request.method == 'GET':
        return jsonify({
            'thresholds': THRESHOLDS,
            'cooldowns': COOLDOWNS,
        })
    
    # POST: Update
    data = request.json or {}
    if "thresholds" in data:
        data["thresholds"] = {int(k): v for k, v in data["thresholds"].items()}
        THRESHOLDS = data['thresholds']
    if 'cooldowns' in data:
        COOLDOWNS = data['cooldowns']
    
    return jsonify({
        'ok': True,
        'thresholds': THRESHOLDS,
        'cooldowns': COOLDOWNS,
    })


if __name__ == '__main__':
    print("Focus Guard läuft auf http://0.0.0.0:5001")
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True, ssl_context="adhoc")
