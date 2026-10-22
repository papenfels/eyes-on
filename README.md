Disclaimer: Everything below and the whole repository is written by AI.

# eyes-on 👁️

Real-time face detection focus monitor with vocal alerts. Built for ADHD, impulsive behavior, and distraction management.

## About

`eyes-on` is a personal focus assistant that monitors your webcam and alerts you when you look away from your desk. Originally tailored for managing ADHD-related attention challenges and impulsive desk-leaving behavior, but designed with **personal AI customization** in mind.

In an era where AI increasingly personalizes to individual needs, this tool embraces that philosophy: instead of generic time-tracking, it uses **your own face** as the signal, **your own voice** (ElevenLabs custom voice clone) for alerts, and **your own thresholds** for what counts as distraction.

### Features

- **Real-time Face Detection**: OpenCV YuNet model running locally on your machine
- **Custom Voice Alerts**: 4-level alert system with rotating voice messages in your own voice
- **Smart Thresholds**: Configurable alert levels (Levels 1-4) at 2s, 5s, 15s, 30s (adjustable)
- **Cooldown System**: Prevents alert fatigue with customizable per-level cooldown periods
- **Quiet Mode**: Cap maximum alert level if you're in a meeting or focused task
- **Video Toggle**: See recognition stats without seeing yourself (privacy-friendly)
- **Dark Mode**: Eye-friendly night mode
- **Pause Button**: Quick pause when you need to step away intentionally
- **Focus Score**: Real-time percentage of time with face detected
- **Comeback Reward**: Plays a motivational message when you refocus

## Use Cases

- **ADHD Management**: Gentle reminders to stay seated and focused
- **Impulsive Behavior**: Catches the impulse to stand up and browse before it happens
- **Deep Work Sessions**: Maintains accountability without guilt-based tracking
- **Flow State Protection**: Gentle nudge back to focus, not aggressive nagging

## Architecture

### Frontend
- **Framework**: Vanilla JavaScript + HTML5
- **Video**: WebRTC getUserMedia API
- **Canvas Processing**: Real-time frame capture at 200ms intervals
- **Storage**: localStorage for settings persistence
- **Theme**: iOS 16 design system (SF Pro font, glassmorphism cards)
- **Size**: ~21 KB minified

### Backend
- **Framework**: Flask 3.1.3 (Python)
- **Face Detection**: OpenCV 5.0.0 + YuNet ONNX model
- **HTTPS**: Self-signed SSL with pyOpenSSL for LAN deployment
- **Audio Generation**: ElevenLabs API (Custom Instant Voice Clone)
- **Model**: eleven_multilingual_v2
- **Audio Storage**: 61 rotating MP3 messages (3.1 MB total)
  - Levels 1-4: 10 messages each + 11 for level 4
  - Comeback phrases: 10 alternate messages
- **Rotation System**: Per-level state tracking (rotation.json)
- **Threading**: Lock-safe detection with background processing

### Infrastructure

```
┌─ Browser
│  └─ Webcam capture → canvas → JPEG base64
│     └─ POST /detect → alert logic + audio
│
└─ Flask Server
   ├─ /detect: Face detection + alert level calculation
   ├─ /alert/<level>: Rotated audio stream (GET)
   ├─ /control: Start/stop monitoring
   └─ /settings: Threshold + cooldown configuration
```

**Deployment**: SSH + background process (`nohup` + `disown`)
**Logs**: `/tmp/focusguard.log` (tail for debugging)
**Config**: localStorage (client) + Flask state (server)

## Customization

Every aspect is designed to be personalized:

1. **Voice**: Record your own ElevenLabs Custom Voice Clone
2. **Thresholds**: Adjust alert levels per your focus needs
3. **Cooldowns**: Set how long before the next alert
4. **Messages**: Replace audio files with your own phrases
5. **Theme**: Dark mode toggle for any time of day

## Installation

### Requirements
- Python 3.8+
- OpenCV 5.0+
- Flask 3.1+
- ElevenLabs API key + Custom Voice ID
- Modern browser with WebRTC support (Firefox/Chrome)

### Setup

```bash
# Clone repo
git clone https://github.com/papenfels/eyes-on.git
cd eyes-on

# Backend
python3 -m venv venv
source venv/bin/activate
pip install flask pyopenssl opencv-python numpy

# Frontend: serve via Flask from /templates/index.html
# Audio files: place in /audio/ directory

# Start
python3 app.py
```

Navigate to `https://localhost:5001` (self-signed cert warning is expected).

## Philosophy

This tool exists because generic productivity apps ignore **who you are**. ADHD management, focus accountability, and alert systems should feel *personal* – not like surveillance.

- **For ADHD**: No judgment, just gentle reminders
- **For AI Era**: Embrace personalization, not one-size-fits-all
- **For Privacy**: Everything runs locally on your network. Your face never leaves your machine.
- **For You**: Customize every threshold, voice, and message

## License

MIT

---

*Built with attention to attention.* ✨
