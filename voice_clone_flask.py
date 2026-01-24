"""
声音克隆工具 - SiliconFlow CosyVoice2
使用用户预置音色API：上传音频到服务器 -> 获取uri -> 用uri生成语音
"""
import os, time, json, requests
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file
from flask_cors import CORS

# 目录配置
BASE_DIR = Path(__file__).parent / "voice_clones"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
VOICES_JSON = BASE_DIR / "voices.json"
CONFIG_FILE = BASE_DIR / "config.json"
BASE_DIR.mkdir(parents=True, exist_ok=True)

# 加载配置
def load_tool_config():
    """加载工具配置文件"""
    default_config = {
        "tts": {
            "api_key": "",
            "base_url": "https://api.siliconflow.cn/v1",
            "model": "FunAudioLLM/CosyVoice2-0.5B"
        },
        "llm_split": {
            "api_key": "",
            "base_url": "https://api.siliconflow.cn/v1",
            "model": "Pro/zai-org/GLM-4.7"
        },
        "llm_optimize": {
            "api_key": "",
            "base_url": "https://api.siliconflow.cn/v1",
            "model": "Pro/zai-org/GLM-4.7"
        },
        "max_subtitle_chars": 15,
        "subtitle": {
            "center_x": 0.5,
            "center_y": 0.92,
            "font": "Microsoft YaHei",
            "size": 0.06
        }
    }
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # 深度合并配置
                for key in default_config:
                    if key in user_config:
                        if isinstance(default_config[key], dict) and isinstance(user_config[key], dict):
                            default_config[key].update(user_config[key])
                        else:
                            default_config[key] = user_config[key]
                # 保留用户自定义的额外配置（如prompts）
                for key in user_config:
                    if key not in default_config:
                        default_config[key] = user_config[key]
        except Exception as e:
            print(f"[WARN] 加载配置文件失败: {e}")
    else:
        # 创建默认配置文件
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 已创建默认配置文件: {CONFIG_FILE}")
    
    return default_config

def save_tool_config(config):
    """保存配置到文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_config():
    """获取最新配置（每次调用都重新读取）"""
    return load_tool_config()

# 兼容旧的system.conf
def load_legacy_config():
    config = {}
    config_path = Path(__file__).parent.parent.parent.parent / "system.conf"
    if config_path.exists():
        for line in open(config_path, 'r', encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('[') and '=' in line:
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip()
    return config

# 加载配置
TOOL_CONFIG = load_tool_config()
LEGACY_CONFIG = load_legacy_config()

# 全局 Whisper 模型缓存（避免每次都加载）
WHISPER_MODEL = None
WHISPER_MODEL_LOCK = None

def get_whisper_model():
    """获取 Whisper 模型（全局缓存，只加载一次）"""
    global WHISPER_MODEL
    
    if WHISPER_MODEL is not None:
        return WHISPER_MODEL
    
    try:
        from faster_whisper import WhisperModel
        
        model_dir = BASE_DIR / "models"
        local_model_path = model_dir / "faster-whisper-small"
        
        if local_model_path.exists() and (local_model_path / "model.bin").exists():
            print("[INFO] 首次加载 Whisper 模型(faster-whisper-small)...")
            WHISPER_MODEL = WhisperModel(str(local_model_path), device="cpu", compute_type="int8")
            print("[INFO] Whisper 模型加载完成！后续调用将直接使用缓存")
            return WHISPER_MODEL
        else:
            print("[ERROR] Whisper 模型文件不存在")
            return None
    except Exception as e:
        print(f"[ERROR] 加载 Whisper 模型失败: {e}")
        return None

# API密钥优先从新配置读取，没有则从旧配置读取
def get_tts_api_key():
    config = get_config()
    return config['tts'].get('api_key') or LEGACY_CONFIG.get('siliconflow_api_key', '')

def get_tts_base_url():
    config = get_config()
    return config['tts'].get('base_url', 'https://api.siliconflow.cn/v1')

def get_llm_split_config():
    config = get_config()
    return config['llm_split']

def get_llm_optimize_config():
    config = get_config()
    return config['llm_optimize']

MAX_SUBTITLE_CHARS = TOOL_CONFIG.get('max_subtitle_chars', 15)

# 预设声音
PRESETS = ["alex", "anna", "bella", "benjamin", "charles", "claire", "david", "diana"]

app = Flask(__name__)
CORS(app)

def load_voices():
    try:
        if VOICES_JSON.exists():
            return json.load(open(VOICES_JSON, 'r', encoding='utf-8'))
    except: pass
    return {}

def save_voices_db(voices):
    with open(VOICES_JSON, 'w', encoding='utf-8') as f:
        json.dump(voices, f, ensure_ascii=False, indent=2)

# ============ API 函数 ============
def upload_voice_to_server(file_path, custom_name, ref_text, model=None):
    """上传音频到SiliconFlow服务器，获取预置音色uri"""
    config = get_config()
    api_key = config['tts'].get('api_key') or LEGACY_CONFIG.get('siliconflow_api_key', '')
    base_url = config['tts'].get('base_url', 'https://api.siliconflow.cn/v1')
    
    # 如果没有指定模型，使用配置中的默认模型
    if model is None:
        model = config['tts'].get('model', 'FunAudioLLM/CosyVoice2-0.5B')
    
    url = f"{base_url}/uploads/audio/voice"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    with open(file_path, 'rb') as f:
        files = {"file": f}
        data = {
            "model": model,
            "customName": custom_name,
            "text": ref_text
        }
        resp = requests.post(url, headers=headers, files=files, data=data, 
                           timeout=60, proxies={"http": None, "https": None})
    
    if resp.status_code == 200:
        result = resp.json()
        return True, result.get("uri", ""), result
    else:
        return False, "", resp.text

def get_server_voices():
    """获取服务器上的用户预置音色列表"""
    config = get_config()
    api_key = config['tts'].get('api_key') or LEGACY_CONFIG.get('siliconflow_api_key', '')
    base_url = config['tts'].get('base_url', 'https://api.siliconflow.cn/v1')
    
    url = f"{base_url}/audio/voice/list"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=30, proxies={"http": None, "https": None})
    if resp.status_code == 200:
        return resp.json()
    return {"result": []}

def delete_server_voice(uri):
    """删除服务器上的预置音色"""
    config = get_config()
    api_key = config['tts'].get('api_key') or LEGACY_CONFIG.get('siliconflow_api_key', '')
    base_url = config['tts'].get('base_url', 'https://api.siliconflow.cn/v1')
    
    url = f"{base_url}/audio/voice/deletions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"uri": uri}, 
                        timeout=30, proxies={"http": None, "https": None})
    return resp.status_code == 200

# ============ STT 语音识别函数 ============
def stt_transcribe(audio_path):
    """使用 faster-whisper 进行语音识别"""
    try:
        model = get_whisper_model()
        if model is None:
            return {"success": False, "message": "Whisper 模型加载失败"}
        
        segments, info = model.transcribe(str(audio_path), language="zh", beam_size=5)
        
        # 收集所有文本
        full_text = ""
        segments_list = []
        for segment in segments:
            full_text += segment.text
            segments_list.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text
            })
        
        # 繁简转换
        try:
            from opencc import OpenCC
            cc = OpenCC('t2s')  # 繁体转简体
            full_text_simplified = cc.convert(full_text)
            for seg in segments_list:
                seg['text'] = cc.convert(seg['text'])
        except:
            print("[WARN] OpenCC 未安装，跳过繁简转换")
            full_text_simplified = full_text
        
        return {
            "success": True,
            "text": full_text_simplified,
            "segments": segments_list,
            "language": info.language,
            "duration": info.duration
        }
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] STT识别失败: {error_detail}")
        return {"success": False, "message": f"识别失败: {str(e)}"}

# ============ HTML界面 ============
HTML = r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Clone Studio</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
            background: #ffffff;
            color: #0f172a;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }

        /* Header */
        .header {
            border-bottom: 1px solid #e2e8f0;
            background: #ffffff;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-inner {
            max-width: 1280px;
            margin: 0 auto;
            padding: 16px 32px;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #000000, #3b3b3b);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 14px;
        }

        .header h1 {
            font-size: 16px;
            font-weight: 600;
            color: #0f172a;
            letter-spacing: -0.01em;
        }

        /* Main Container */
        .container {
            max-width: 1280px;
            margin: 0 auto;
            padding: 48px 32px;
        }

        .grid {
            display: grid;
            grid-template-columns: 1fr 400px;
            gap: 24px;
            margin-bottom: 24px;
            align-items: stretch;
        }

        .grid-bottom {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }

        /* Cards */
        .card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 24px;
            transition: border-color 0.2s;
        }

        .card:hover {
            border-color: #cbd5e1;
        }

        .card-title {
            font-size: 14px;
            font-weight: 600;
            color: #0f172a;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Form Elements */
        .form-group {
            margin-bottom: 12px;
        }

        .form-group:last-child {
            margin-bottom: 0;
        }

        label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: #475569;
            margin-bottom: 8px;
        }

        input[type="text"],
        select,
        textarea {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            font-family: inherit;
            color: #0f172a;
            background: #ffffff;
            transition: all 0.2s;
        }

        input[type="text"]:focus,
        select:focus,
        textarea:focus {
            outline: none;
            border-color: #0f172a;
            box-shadow: 0 0 0 3px rgba(15, 23, 42, 0.05);
        }

        textarea {
            min-height: 160px;
            resize: vertical;
            line-height: 1.6;
        }

        input[type="file"] {
            width: 100%;
            padding: 12px;
            border: 2px dashed #e2e8f0;
            border-radius: 8px;
            font-size: 13px;
            cursor: pointer;
            background: #f8fafc;
            color: #64748b;
            transition: all 0.2s;
            display: block;
            position: relative;
            z-index: 1;
        }

        input[type="file"]:hover {
            border-color: #cbd5e1;
            background: #f1f5f9;
        }

        /* Range Slider */
        .slider-group {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        input[type="range"] {
            flex: 1;
            height: 6px;
            border-radius: 3px;
            background: #e2e8f0;
            outline: none;
            -webkit-appearance: none;
        }

        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: #0f172a;
            cursor: pointer;
            transition: transform 0.2s;
        }

        input[type="range"]::-webkit-slider-thumb:hover {
            transform: scale(1.1);
        }

        .slider-value {
            min-width: 40px;
            text-align: center;
            font-weight: 600;
            font-size: 14px;
            color: #0f172a;
        }

        /* Buttons */
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            font-family: inherit;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }

        .btn-primary {
            background: #0f172a;
            color: #ffffff;
        }

        .btn-primary:hover:not(:disabled) {
            background: #1e293b;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
        }

        .btn-secondary {
            background: #ffffff;
            color: #0f172a;
            border: 1px solid #e2e8f0;
        }

        .btn-secondary:hover:not(:disabled) {
            background: #f8fafc;
            border-color: #cbd5e1;
        }

        .btn-danger {
            background: #dc2626;
            color: #ffffff;
            font-size: 13px;
            padding: 8px 16px;
        }

        .btn-danger:hover:not(:disabled) {
            background: #b91c1c;
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
        }

        .btn-group {
            display: flex;
            gap: 12px;
            margin-top: 12px;
        }

        /* Voice Selection */
        .voice-section {
            margin-bottom: 12px;
        }

        .voice-section:last-child {
            margin-bottom: 0;
        }

        .section-label {
            font-size: 11px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }

        .voice-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 6px;
        }

        .voice-btn {
            padding: 6px 4px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            background: #ffffff;
            cursor: pointer;
            text-align: center;
            font-size: 11px;
            font-weight: 500;
            color: #475569;
            transition: all 0.2s;
            position: relative;
            overflow: hidden;
        }

        .voice-btn:hover {
            border-color: #0f172a;
            background: #f8fafc;
        }

        .voice-btn.selected {
            background: #0f172a;
            color: #ffffff;
            border-color: #0f172a;
        }

        .voice-badge {
            position: absolute;
            top: 2px;
            right: 2px;
            background: #10b981;
            color: #ffffff;
            font-size: 8px;
            padding: 1px 4px;
            border-radius: 3px;
            font-weight: 600;
        }

        /* Messages */
        .message {
            padding: 12px 16px;
            border-radius: 8px;
            margin-top: 16px;
            font-size: 13px;
            display: none;
        }

        .message.show {
            display: block;
        }

        .message.success {
            background: #d1fae5;
            color: #065f46;
            border: 1px solid #6ee7b7;
        }

        .message.error {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
        }

        /* Audio Player */
        audio {
            width: 100%;
            margin-top: 16px;
            border-radius: 8px;
        }

        /* Tip Box */
        .tip {
            background: #fef3c7;
            border: 1px solid #fde68a;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 13px;
            color: #92400e;
        }

        /* Empty State */
        .empty {
            text-align: center;
            padding: 32px 16px;
            color: #94a3b8;
            font-size: 13px;
            background: #f8fafc;
            border-radius: 8px;
        }

        /* Loading Spinner */
        .spinner {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top-color: #ffffff;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Two Column Form */
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        /* Responsive */
        @media (max-width: 1024px) {
            .grid {
                grid-template-columns: 1fr;
            }

            .grid-bottom {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 640px) {
            .container {
                padding: 24px 16px;
            }

            .header-inner {
                padding: 12px 16px;
            }

            .voice-grid {
                grid-template-columns: repeat(3, 1fr);
            }

            .form-row {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-inner">
            <div class="logo">V</div>
            <h1>Voice Clone Studio</h1>
        </div>
    </div>

    <div class="container">
        <!-- Top Grid: Text Input + Settings & Voice Selection -->
        <div class="grid">
            <!-- Left: Text Input -->
            <div class="card">
                <h2 class="card-title">📝 输入文字</h2>
                <div class="form-group">
                    <textarea id="ttsText" placeholder="在这里输入要转换的文字..."></textarea>
                </div>
                <!-- 语气标记提示 -->
                <div style="font-size:11px;color:#64748b;margin-bottom:8px;line-height:1.8;background:#f8fafc;padding:10px;border-radius:8px;">
                    💡 <b>细粒度标记</b> <span style="color:#10b981;font-size:9px;">✅官方Demo验证</span> <span style="color:#94a3b8;font-size:9px;">（可放句中）</span><br>
                    <code style="background:#d1fae5;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;" onclick="insertTag('[breath]')">[breath]</code> 呼吸
                    <code style="background:#d1fae5;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;" onclick="insertTag('[laughter]')">[laughter]</code> 笑声
                    <code style="background:#d1fae5;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;" onclick="insertTag('&lt;strong&gt;')">&lt;strong&gt;</code>
                    <code style="background:#d1fae5;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;" onclick="insertTag('&lt;/strong&gt;')">&lt;/strong&gt;</code> 强调
                    <code style="background:#d1fae5;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;" onclick="insertTag('&lt;laughter&gt;')">&lt;laughter&gt;</code>
                    <code style="background:#d1fae5;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;" onclick="insertTag('&lt;/laughter&gt;')">&lt;/laughter&gt;</code> 边笑边说
                    <br>
                    <span style="color:#ef4444;font-size:9px;">⚠️ tokenizer.py有但官方Demo未验证（不稳定，可能不生效）：</span>
                    <code style="background:#fee2e2;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;color:#991b1b;" onclick="insertTag('[sigh]')">[sigh]</code>
                    <code style="background:#fee2e2;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;color:#991b1b;" onclick="insertTag('[mn]')">[mn]</code>
                    <code style="background:#fee2e2;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;color:#991b1b;" onclick="insertTag('[cough]')">[cough]</code>
                    <code style="background:#fee2e2;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;color:#991b1b;" onclick="insertTag('[noise]')">[noise]</code>
                    <code style="background:#fee2e2;padding:2px 6px;border-radius:3px;cursor:pointer;margin:2px;color:#991b1b;" onclick="insertTag('[lipsmack]')">[lipsmack]</code>
                    <br>
                    📌 <b>情感/语气指令</b> <span style="color:#f59e0b;font-size:9px;">⚠️官方Demo有示例但效果不稳定</span> <span style="color:#94a3b8;font-size:9px;">（只能放开头）</span><br>
                    <code style="background:#fef3c7;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('用开心的语气说&lt;|endofprompt|&gt;')">开心</code>
                    <code style="background:#fef3c7;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('用伤心的语气说&lt;|endofprompt|&gt;')">伤心</code>
                    <code style="background:#fef3c7;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('用惊讶的语气说&lt;|endofprompt|&gt;')">惊讶</code>
                    <code style="background:#fef3c7;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('用生气的语气说&lt;|endofprompt|&gt;')">生气</code>
                    <code style="background:#fef3c7;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('用恐惧的情感表达&lt;|endofprompt|&gt;')">恐惧</code>
                    <code style="background:#fef3c7;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('冷静&lt;|endofprompt|&gt;')">冷静</code>
                    <code style="background:#fef3c7;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('严肃&lt;|endofprompt|&gt;')">严肃</code>
                    <br>
                    <code style="background:#e0f2fe;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('神秘&lt;|endofprompt|&gt;')">神秘</code>
                    <code style="background:#e0f2fe;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('凶猛&lt;|endofprompt|&gt;')">凶猛</code>
                    <code style="background:#e0f2fe;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('好奇&lt;|endofprompt|&gt;')">好奇</code>
                    <code style="background:#e0f2fe;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('优雅&lt;|endofprompt|&gt;')">优雅</code>
                    <code style="background:#e0f2fe;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('孤独&lt;|endofprompt|&gt;')">孤独</code>
                    <code style="background:#e5e7eb;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('快速&lt;|endofprompt|&gt;')">快速</code>
                    <code style="background:#e5e7eb;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('非常快速&lt;|endofprompt|&gt;')">非常快速</code>
                    <code style="background:#e5e7eb;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('慢速&lt;|endofprompt|&gt;')">慢速</code>
                    <br>
                    <code style="background:#dbeafe;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('用四川话说&lt;|endofprompt|&gt;')">四川话</code>
                    <code style="background:#dbeafe;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('用粤语说这句话&lt;|endofprompt|&gt;')">粤语</code>
                    <code style="background:#dbeafe;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('上海话&lt;|endofprompt|&gt;')">上海话</code>
                    <code style="background:#dbeafe;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;margin:2px;" onclick="insertAtStart('模仿机器人风格&lt;|endofprompt|&gt;')">机器人</code>
                    <br>
                    <span style="color:#64748b;font-size:10px;">📝 官方示例：在他讲述那个荒诞故事的过程中，他突然<b>[laughter]</b>停下来，因为他自己也被逗笑了<b>[laughter]</b>。</span><br>
                    <span style="color:#64748b;font-size:10px;">📝 官方示例：追求卓越不是终点，它需要你每天都<b>&lt;strong&gt;</b>付出<b>&lt;/strong&gt;</b>和<b>&lt;strong&gt;</b>精进<b>&lt;/strong&gt;</b>，最终才能达到巅峰。</span><br>
                    <span style="color:#64748b;font-size:10px;">📝 官方示例：当你用心去倾听一首音乐时<b>[breath]</b>，你会开始注意到那些细微的音符变化<b>[breath]</b>，并通过它们感受到音乐背后的情感。</span>
                </div>
                <div class="btn-group" style="display:flex;gap:8px;flex-wrap:wrap;">
                    <button class="btn btn-primary" id="genBtn" onclick="generate()">生成语音</button>
                    <button class="btn btn-secondary" id="aiOptBtn" onclick="aiOptimizeText()">AI优化</button>
                    <button class="btn btn-secondary" id="sttBtn" onclick="showSTTModal()">🎤 语音识别</button>
                    <button class="btn btn-secondary" id="davinciConfigBtn" onclick="showDavinciConfig()">⚙️ 达芬奇</button>
                    <button class="btn btn-secondary" onclick="showApiConfig()">🔑 API设置</button>
                </div>
                <div id="genMsg" class="message"></div>
                
                <!-- 生成结果显示区域 -->
                <div id="resultArea" style="display:none;margin-top:16px;padding:16px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;">
                    <h3 style="font-size:14px;font-weight:600;margin:0 0 12px 0;color:#0f172a;">📊 生成结果</h3>
                    
                    <!-- 音频播放器 -->
                    <div style="margin-bottom:12px;">
                        <audio id="player" controls style="width:100%;"></audio>
                    </div>
                    
                    <!-- 识别文本显示 -->
                    <div id="recognizedTextArea" style="display:none;margin-bottom:12px;">
                        <label style="font-size:12px;font-weight:500;color:#64748b;display:block;margin-bottom:6px;">识别文本</label>
                        <div style="padding:10px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;font-size:13px;line-height:1.6;max-height:120px;overflow-y:auto;" id="recognizedText"></div>
                    </div>
                    
                    <!-- 字幕预览 -->
                    <div id="subtitlePreviewArea" style="display:none;margin-bottom:12px;">
                        <label style="font-size:12px;font-weight:500;color:#64748b;display:block;margin-bottom:6px;">字幕预览</label>
                        <div style="padding:10px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;font-size:12px;line-height:1.8;max-height:150px;overflow-y:auto;font-family:monospace;" id="subtitlePreview"></div>
                    </div>
                    
                    <!-- 下载按钮 -->
                    <div style="display:flex;gap:8px;flex-wrap:wrap;">
                        <a id="audioDownload" href="#" download class="btn btn-secondary" style="text-decoration:none;display:inline-flex;align-items:center;gap:4px;">
                            🎵 下载音频
                        </a>
                        <a id="srtDownload" href="#" download class="btn btn-secondary" style="text-decoration:none;display:none;align-items:center;gap:4px;">
                            📄 下载字幕
                        </a>
                        <button class="btn btn-secondary" id="davinciBtn" onclick="importToDavinci()" style="display:none;">
                            🎬 导入达芬奇
                        </button>
                    </div>
                </div>
                
                <!-- 达芬奇配置弹窗 -->
                <div id="davinciConfigModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center;">
                    <div style="background:#fff;padding:24px;border-radius:12px;max-width:500px;width:90%;">
                        <h3 style="margin:0 0 16px 0;font-size:16px;">⚙️ 达芬奇路径设置</h3>
                        <p style="font-size:13px;color:#64748b;margin-bottom:12px;">请选择达芬奇安装目录下的 Resolve.exe 文件</p>
                        <div style="margin-bottom:12px;">
                            <input type="text" id="resolveExePath" placeholder="例如: D:\\DaVinci Resolve\\Resolve.exe" style="width:100%;">
                        </div>
                        <div id="davinciConfigMsg" class="message" style="margin-bottom:12px;"></div>
                        <div style="display:flex;gap:8px;justify-content:flex-end;">
                            <button class="btn btn-secondary" onclick="hideDavinciConfig()">取消</button>
                            <button class="btn btn-primary" onclick="saveDavinciConfig()">保存</button>
                        </div>
                    </div>
                </div>
                
                <!-- STT 语音识别弹窗 -->
                <div id="sttModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center;">
                    <div style="background:#fff;padding:24px;border-radius:12px;max-width:600px;width:90%;">
                        <h3 style="margin:0 0 16px 0;font-size:16px;">🎤 语音识别 (STT)</h3>
                        <p style="font-size:13px;color:#64748b;margin-bottom:12px;">上传音频文件，自动识别为文字</p>
                        <div style="margin-bottom:12px;">
                            <label style="font-size:12px;color:#64748b;">选择音频文件</label>
                            <input type="file" id="sttAudioFile" accept="audio/*" style="width:100%;">
                        </div>
                        <div id="sttResult" style="display:none;margin-bottom:12px;padding:12px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;">
                            <label style="font-size:12px;color:#64748b;margin-bottom:8px;display:block;">识别结果</label>
                            <textarea id="sttResultText" style="width:100%;min-height:120px;"></textarea>
                        </div>
                        <div id="sttMsg" class="message" style="margin-bottom:12px;"></div>
                        <div style="display:flex;gap:8px;justify-content:flex-end;">
                            <button class="btn btn-secondary" onclick="hideSTTModal()">取消</button>
                            <button class="btn btn-primary" id="sttRecognizeBtn" onclick="recognizeAudio()">开始识别</button>
                            <button class="btn btn-secondary" id="sttDownloadBtn" onclick="downloadSTTSubtitle()" style="display:none;">📄 下载字幕</button>
                            <button class="btn btn-primary" id="sttInsertBtn" onclick="insertSTTResult()" style="display:none;">插入文本</button>
                        </div>
                    </div>
                </div>
                
                <!-- API配置弹窗 -->
                <div id="apiConfigModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center;">
                    <div style="background:#fff;padding:24px;border-radius:12px;max-width:600px;width:95%;max-height:90vh;overflow-y:auto;">
                        <h3 style="margin:0 0 16px 0;font-size:16px;">🔑 API配置</h3>
                        
                        <!-- TTS配置 -->
                        <div style="background:#f8fafc;padding:12px;border-radius:8px;margin-bottom:12px;">
                            <div style="font-weight:600;margin-bottom:8px;color:#1e293b;">🎙️ TTS语音合成</div>
                            <div style="display:grid;gap:8px;">
                                <div>
                                    <label style="font-size:12px;color:#64748b;">API密钥</label>
                                    <input type="password" id="ttsApiKey" placeholder="sk-xxx" style="width:100%;">
                                </div>
                                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                                    <div>
                                        <label style="font-size:12px;color:#64748b;">端点</label>
                                        <input type="text" id="ttsBaseUrl" placeholder="https://api.siliconflow.cn/v1" style="width:100%;">
                                    </div>
                                    <div>
                                        <label style="font-size:12px;color:#64748b;">模型</label>
                                        <input type="text" id="ttsModel" placeholder="FunAudioLLM/CosyVoice2-0.5B" style="width:100%;">
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- LLM分割配置 -->
                        <div style="background:#f0fdf4;padding:12px;border-radius:8px;margin-bottom:12px;">
                            <div style="font-weight:600;margin-bottom:8px;color:#1e293b;">✂️ AI字幕分割</div>
                            <div style="display:grid;gap:8px;">
                                <div>
                                    <label style="font-size:12px;color:#64748b;">API密钥 <span style="color:#94a3b8;">(留空则用TTS密钥)</span></label>
                                    <input type="password" id="llmSplitApiKey" placeholder="留空则使用TTS密钥" style="width:100%;">
                                </div>
                                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                                    <div>
                                        <label style="font-size:12px;color:#64748b;">端点</label>
                                        <input type="text" id="llmSplitBaseUrl" placeholder="https://api.siliconflow.cn/v1" style="width:100%;">
                                    </div>
                                    <div>
                                        <label style="font-size:12px;color:#64748b;">模型</label>
                                        <input type="text" id="llmSplitModel" placeholder="Pro/zai-org/GLM-4.7" style="width:100%;">
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- LLM优化配置 -->
                        <div style="background:#fef3c7;padding:12px;border-radius:8px;margin-bottom:12px;">
                            <div style="font-weight:600;margin-bottom:8px;color:#1e293b;">✨ AI文本优化</div>
                            <div style="display:grid;gap:8px;">
                                <div>
                                    <label style="font-size:12px;color:#64748b;">API密钥 <span style="color:#94a3b8;">(留空则用TTS密钥)</span></label>
                                    <input type="password" id="llmOptApiKey" placeholder="留空则使用TTS密钥" style="width:100%;">
                                </div>
                                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                                    <div>
                                        <label style="font-size:12px;color:#64748b;">端点</label>
                                        <input type="text" id="llmOptBaseUrl" placeholder="https://api.siliconflow.cn/v1" style="width:100%;">
                                    </div>
                                    <div>
                                        <label style="font-size:12px;color:#64748b;">模型</label>
                                        <input type="text" id="llmOptModel" placeholder="Pro/zai-org/GLM-4.7" style="width:100%;">
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div id="apiConfigMsg" class="message" style="margin-bottom:12px;"></div>
                        <div style="display:flex;gap:8px;justify-content:flex-end;">
                            <button class="btn btn-secondary" onclick="hideApiConfig()">取消</button>
                            <button class="btn btn-primary" onclick="saveApiConfig()">保存</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right: Settings & Voice Selection -->
            <div style="display: flex; flex-direction: column; gap: 16px;">
                <!-- Settings Card -->
                <div class="card" style="flex-shrink: 0; padding: 16px;">
                    <h2 class="card-title" style="margin-bottom: 12px;">⚙️ 设置</h2>
                    <div class="form-row">
                        <div class="form-group">
                            <label>模型</label>
                            <select id="modelSelect" onchange="onModelChange()">
                                <option value="cosyvoice">CosyVoice2 - 情感控制</option>
                                <option value="indextts2">IndexTTS-2 - 零样本克隆</option>
                                <option value="moss">MOSS-TTSD - 长文本</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>语速</label>
                            <div class="slider-group">
                                <input type="range" id="speed" min="0.5" max="2" step="0.1" value="1"
                                       oninput="document.getElementById('speedVal').textContent=this.value">
                                <span class="slider-value" id="speedVal">1</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Voice Selection Card -->
                <div class="card" style="flex: 1; overflow-y: auto; max-height: 200px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                        <h2 class="card-title" style="margin: 0;">🎤 选择声音</h2>
                        <button class="btn btn-secondary" onclick="loadVoices()" style="padding: 4px 10px; font-size: 12px;">刷新</button>
                    </div>

                    <div class="voice-section">
                        <div class="section-label">我的克隆声音</div>
                        <div class="voice-grid" id="cloneVoices"></div>
                    </div>

                    <div class="voice-section">
                        <div class="section-label">预设声音</div>
                        <div class="voice-grid" id="presetVoices"></div>
                    </div>
                </div>
                
                <!-- AI优化提示词 -->
                <div class="card" style="margin-top: 12px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                        <h2 class="card-title" style="margin: 0; font-size: 13px;">🤖 AI优化提示词</h2>
                        <select id="promptType" onchange="switchPromptType()" style="padding:4px 8px;font-size:11px;border-radius:4px;border:1px solid #e2e8f0;">
                            <option value="cosyvoice">CosyVoice2</option>
                            <option value="indextts2">IndexTTS-2</option>
                            <option value="moss">MOSS-TTSD</option>
                        </select>
                    </div>
                    <textarea id="systemPrompt" style="min-height:120px;font-size:11px;line-height:1.5;font-family:monospace;"></textarea>
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
                        <span style="font-size:10px;color:#94a3b8;">点击"AI优化"按钮时使用此提示词</span>
                        <button class="btn btn-secondary" onclick="savePrompt()" style="padding:4px 10px;font-size:11px;">💾 保存</button>
                    </div>
                    <div id="promptMsg" class="message" style="margin-top:8px;"></div>
                </div>
                
                <!-- AI 分割提示词 -->
                <div class="card" style="margin-top: 12px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                        <h2 class="card-title" style="margin: 0; font-size: 13px;">✂️ AI字幕分割提示词</h2>
                        <span id="splitModelName" style="font-size:10px;color:#94a3b8;">模型: 加载中...</span>
                    </div>
                    <textarea id="splitPrompt" style="min-height:120px;font-size:11px;line-height:1.5;font-family:monospace;"></textarea>
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
                        <span style="font-size:10px;color:#94a3b8;">生成字幕时自动调用，将文本分割成短句</span>
                        <button class="btn btn-secondary" onclick="saveSplitPrompt()" style="padding:4px 10px;font-size:11px;">💾 保存</button>
                    </div>
                    <div id="splitPromptMsg" class="message" style="margin-top:8px;"></div>
                </div>
            </div>
        </div>

        <!-- Bottom Grid: Upload & Manage -->
        <div class="grid-bottom">
            <!-- Upload Card -->
            <div class="card">
                <h2 class="card-title">☁️ 上传声音</h2>
                <div class="tip">📌 音频30秒以内 | 清晰无噪音 | 单人说话 | 情感自然 | 准确填写音频内容</div>

                <div class="form-row">
                    <div class="form-group">
                        <label>音频文件</label>
                        <input type="file" id="refAudio" accept=".mp3,.wav,.pcm,.opus,audio/*" style="display:none;" onchange="updateFileName()">
                        <button type="button" class="btn btn-secondary" onclick="document.getElementById('refAudio').click()" style="width:100%;">📁 选择音频文件</button>
                        <div id="fileName" style="font-size:12px;color:#64748b;margin-top:4px;"></div>
                    </div>
                    <div class="form-group">
                        <label>声音名称</label>
                        <input type="text" id="voiceName" placeholder="英文或拼音">
                    </div>
                </div>

                <div class="form-group">
                    <label>音频中说的话</label>
                    <textarea id="refText" placeholder="准确输入音频内容" style="min-height: 60px;"></textarea>
                </div>

                <button class="btn btn-primary" id="uploadBtn" onclick="uploadVoice()">上传</button>
                <div id="saveMsg" class="message"></div>
            </div>

            <!-- Manage Card -->
            <div class="card">
                <h2 class="card-title">🗑️ 管理声音</h2>
                <div class="form-group">
                    <label>选择要删除的声音</label>
                    <select id="delSelect">
                        <option value="">-- 选择 --</option>
                    </select>
                </div>
                <button class="btn btn-danger" onclick="deleteVoice()">删除</button>
                <div id="delMsg" class="message"></div>
            </div>
        </div>
    </div>

    <script>
        let selectedVoice = null;
        let voiceList = [];
        
        // AI优化提示词（默认值）
        const DEFAULT_PROMPTS = {
            cosyvoice: `你是一位资深配音导演，正在为视频配音做语气标注。你的任务是让文字读起来像真人说话一样自然。

【官方Demo验证过的稳定标记】（只用这4个！）
- [breath] 呼吸/停顿 - 说话人换气、思考、转折处
- [laughter] 笑声 - 开心、幽默、自嘲时发出笑声
- <strong>词</strong> - 强调重点词
- <laughter>文字</laughter> - 边笑边说

【情感指令】（只能放最开头，效果不稳定但可以尝试）
如果整体情感明显，可以在开头加：
- 用开心的语气说<|endofprompt|>
- 用伤心的语气说<|endofprompt|>
- 用惊讶的语气说<|endofprompt|>
- 用生气的语气说<|endofprompt|>

【你的工作流程】
1. 通读全文，感受情感基调
2. 如果整体情感明显，在开头加情感指令
3. 逐句分析，在合适位置插入细粒度标记
4. 删除所有空格

【重要规则】
1. 每2-3句话至少一个[breath]
2. 幽默/开心处加[laughter]
3. 关键词用<strong></strong>
4. 绝对不要加空格！
5. 情感指令只能放最开头！

直接输出优化后的文本，不要解释。`,
            indextts2: `你是一位资深配音导演，正在为 IndexTTS-2 语音合成优化文本。IndexTTS-2 擅长零样本声音克隆和自然情感表达。

【IndexTTS-2 的特点】
- 不支持细粒度标记（没有 [breath]、[laughter] 等）
- 自动识别标点符号控制节奏和停顿
- 自然情感表达能力强，无需特殊标记
- 适合长文本合成

【你的工作流程】
1. 通读全文，理解情感基调
2. 调整标点符号，控制说话节奏：
   - 逗号：短停顿
   - 句号：正常停顿
   - 感叹号：情绪强烈
   - 问号：疑问语气
   - 省略号：思考、犹豫
3. 删除所有空格
4. 避免过长句子（每句不超过30字）

【重要规则】
1. 不要添加任何特殊标记！
2. 只用标点符号控制节奏
3. 删除所有空格
4. 保持文本自然流畅

直接输出优化后的文本，不要解释。`,
            moss: `你是专业配音演员和语音导演。任务：深度分析文本，添加语气标记让语音更自然生动。

【MOSS-TTSD 专用标记】
- [laughter] 笑声：开心、幽默、自嘲处
- [breath] 呼吸停顿：思考、转折、情绪酝酿处
- [S1] [S2] 说话人切换：对话场景（MOSS 支持双人对话）

【格式要求】
- 删除所有空格（官方要求）
- 标点符号正常使用
- 如果是对话，用 [S1] 和 [S2] 标记不同说话人

【示例】
原文：今天真是太开心了，终于放假了
优化：[breath]今天真是太开心了，[laughter]终于放假了

对话示例：
原文：你好吗？我很好，谢谢！
优化：[S1]你好吗？[S2]我很好，谢谢！

直接返回优化后的文本，不要任何解释。`
        };
        
        // 用户保存的提示词
        let savedPrompts = { cosyvoice: '', indextts2: '', moss: '' };
        let savedSplitPrompt = '';  // AI 分割提示词
        
        async function loadSavedPrompts() {
            try {
                const res = await fetch('/api/prompts');
                const data = await res.json();
                console.log('API返回:', data);
                if (data.success && data.prompts) {
                    // 合并而不是覆盖
                    if (data.prompts.cosyvoice) savedPrompts.cosyvoice = data.prompts.cosyvoice;
                    if (data.prompts.moss) savedPrompts.moss = data.prompts.moss;
                    if (data.prompts.indextts2) savedPrompts.indextts2 = data.prompts.indextts2;
                    if (data.prompts.split) {
                        savedSplitPrompt = data.prompts.split;
                        document.getElementById('splitPrompt').value = savedSplitPrompt;
                    }
                    console.log('加载的提示词:', savedPrompts);
                }
                
                // 加载 AI 分割模型名称
                if (data.config && data.config.llm_split && data.config.llm_split.model) {
                    document.getElementById('splitModelName').textContent = '模型: ' + data.config.llm_split.model;
                }
            } catch(e) {
                console.error('加载提示词失败:', e);
            }
        }
        
        function switchPromptType() {
            const type = document.getElementById('promptType').value;
            // 优先用保存的（检查是否存在且不为空），没有则用默认的
            const prompt = (savedPrompts[type] && savedPrompts[type].trim()) ? savedPrompts[type] : DEFAULT_PROMPTS[type];
            document.getElementById('systemPrompt').value = prompt;
        }
        
        async function savePrompt() {
            const type = document.getElementById('promptType').value;
            const prompt = document.getElementById('systemPrompt').value;
            const msgDiv = document.getElementById('promptMsg');
            
            try {
                const res = await fetch('/api/prompts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type, prompt })
                });
                const data = await res.json();
                if (data.success) {
                    savedPrompts[type] = prompt;
                    showMsg(msgDiv, '✅ 已保存', true);
                } else {
                    showMsg(msgDiv, '保存失败: ' + data.message, false);
                }
            } catch(e) {
                showMsg(msgDiv, '保存失败: ' + e, false);
            }
        }
        
        async function saveSplitPrompt() {
            const prompt = document.getElementById('splitPrompt').value;
            const msgDiv = document.getElementById('splitPromptMsg');
            
            try {
                const res = await fetch('/api/prompts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type: 'split', prompt })
                });
                const data = await res.json();
                if (data.success) {
                    savedSplitPrompt = prompt;
                    showMsg(msgDiv, '✅ 已保存', true);
                } else {
                    showMsg(msgDiv, '保存失败: ' + data.message, false);
                }
            } catch(e) {
                showMsg(msgDiv, '保存失败: ' + e, false);
            }
        }
        
        function resetPrompt() {
            const type = document.getElementById('promptType').value;
            document.getElementById('systemPrompt').value = DEFAULT_PROMPTS[type];
        }

        async function loadVoices() {
            console.log('[DEBUG] 开始加载声音列表...');
            try {
                // 先加载保存的提示词
                await loadSavedPrompts();
                
                console.log('[DEBUG] 请求 /api/voices...');
                const res = await fetch('/api/voices');
                const data = await res.json();
                console.log('[DEBUG] 收到数据:', data);
                
                // 保存所有音色数据
                window.cosyvoiceClones = data.clones || [];
                window.indextts2Clones = data.indextts2_clones || [];
                
                console.log('[DEBUG] CosyVoice2 音色数量:', window.cosyvoiceClones.length);
                console.log('[DEBUG] IndexTTS-2 音色数量:', window.indextts2Clones.length);
                console.log('[DEBUG] 预设声音数量:', (data.presets || []).length);

                // 保存预设音色
                window.presets = data.presets || [];
                
                // 根据当前选择的模型显示对应的音色
                updateVoiceList();
                
                console.log('[DEBUG] 声音加载完成！');
                
                // 初始化提示词
                switchPromptType();
            } catch(e) {
                console.error('[ERROR] 加载失败:', e);
                alert('加载声音失败: ' + e.message);
            }
        }
        
        function updateVoiceList() {
            // 获取当前选择的模型
            const modelSelect = document.getElementById('modelSelect');
            const currentModel = modelSelect ? modelSelect.value : 'cosyvoice';
            
            console.log('[DEBUG] 当前模型:', currentModel);
            
            // 根据模型选择对应的音色列表
            let voiceList = [];
            if (currentModel === 'indextts2') {
                voiceList = window.indextts2Clones || [];
            } else {
                voiceList = window.cosyvoiceClones || [];
            }
            
            console.log('[DEBUG] 显示音色数量:', voiceList.length);
            
            const cloneDiv = document.getElementById('cloneVoices');
            const presetDiv = document.getElementById('presetVoices');
            const delSelect = document.getElementById('delSelect');
            
            cloneDiv.innerHTML = '';
            presetDiv.innerHTML = '';
            if (delSelect) {
                delSelect.innerHTML = '<option value="">-- 选择 --</option>';
            }

            if (voiceList.length === 0) {
                cloneDiv.innerHTML = '<div class="empty">还没有克隆声音，请先上传</div>';
            } else {
                voiceList.forEach((v, index) => {
                    const div = document.createElement('div');
                    div.className = 'voice-btn clone';
                    div.innerHTML = `<span class="voice-badge">云</span>${v.customName || v.name}`;
                    div.onclick = () => selectVoice('clone', v.uri, v.customName || v.name, div);
                    cloneDiv.appendChild(div);

                    if (delSelect) {
                        const opt = document.createElement('option');
                        opt.value = v.uri;
                        opt.textContent = v.customName || v.name;
                        delSelect.appendChild(opt);
                    }
                });
            }

            const presets = window.presets || [];
            presets.forEach((name, index) => {
                const div = document.createElement('div');
                div.className = 'voice-btn preset';
                div.textContent = name;
                div.onclick = () => selectVoice('preset', name, name, div);
                presetDiv.appendChild(div);
            });
        }

        function selectVoice(type, value, name, el) {
            document.querySelectorAll('.voice-btn').forEach(x => x.classList.remove('selected'));
            el.classList.add('selected');
            selectedVoice = { type, value, name };
        }

        async function uploadVoice() {
            const file = document.getElementById('refAudio').files[0];
            const refText = document.getElementById('refText').value.trim();
            const name = document.getElementById('voiceName').value.trim();
            const msgDiv = document.getElementById('saveMsg');
            const btn = document.getElementById('uploadBtn');
            
            // 获取当前选择的模型
            const currentModel = document.getElementById('modelSelect').value;

            if (!file) { showMsg(msgDiv, '请选择音频文件', false); return; }
            if (!refText) { showMsg(msgDiv, '请输入参考音频中说的话', false); return; }
            if (!name) { showMsg(msgDiv, '请输入声音名称', false); return; }
            if (!/^[a-zA-Z0-9_-]+$/.test(name)) { showMsg(msgDiv, '名称只能包含英文、数字、下划线、横线', false); return; }

            btn.disabled = true;
            btn.innerHTML = '上传中... <span class="spinner"></span>';

            const form = new FormData();
            form.append('audio', file);
            form.append('text', refText);
            form.append('name', name);
            form.append('model', currentModel);  // 传递当前选择的模型

            try {
                const res = await fetch('/api/upload', { method: 'POST', body: form });
                const data = await res.json();
                showMsg(msgDiv, data.message, data.success);
                if (data.success) {
                    document.getElementById('voiceName').value = '';
                    document.getElementById('refText').value = '';
                    loadVoices();
                }
            } catch(e) {
                showMsg(msgDiv, '上传失败: ' + e, false);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '上传';
            }
        }

        async function generate() {
            const text = document.getElementById('ttsText').value.trim();
            const speed = document.getElementById('speed').value;
            const model = document.getElementById('modelSelect').value;
            const msgDiv = document.getElementById('genMsg');
            const btn = document.getElementById('genBtn');
            const resultArea = document.getElementById('resultArea');
            const player = document.getElementById('player');

            if (!selectedVoice) { showMsg(msgDiv, '请先选择一个声音', false); return; }
            if (!text) { showMsg(msgDiv, '请输入文字', false); return; }

            btn.disabled = true;
            btn.innerHTML = '生成中... <span class="spinner"></span>';
            msgDiv.className = 'message';
            resultArea.style.display = 'none';

            try {
                const res = await fetch('/api/tts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text,
                        speed: parseFloat(speed),
                        voice_type: selectedVoice.type,
                        voice_value: selectedVoice.value,
                        model: model
                    })
                });
                const data = await res.json();
                showMsg(msgDiv, data.message, data.success);
                if (data.success) {
                    // 显示结果区域
                    resultArea.style.display = 'block';
                    
                    // 设置音频播放器
                    player.src = data.audio_url + '?t=' + Date.now();
                    player.play();
                    
                    // 显示识别文本（如果有）
                    const recognizedTextArea = document.getElementById('recognizedTextArea');
                    const recognizedText = document.getElementById('recognizedText');
                    if (data.recognized_text) {
                        recognizedText.textContent = data.recognized_text;
                        recognizedTextArea.style.display = 'block';
                    } else {
                        recognizedTextArea.style.display = 'none';
                    }
                    
                    // 显示字幕预览
                    const subtitlePreviewArea = document.getElementById('subtitlePreviewArea');
                    const subtitlePreview = document.getElementById('subtitlePreview');
                    if (data.segments && data.segments.length > 0) {
                        let srtContent = '';
                        data.segments.forEach((seg, i) => {
                            srtContent += `${i + 1}\\n`;
                            srtContent += `${formatSrtTime(seg.start)} --> ${formatSrtTime(seg.end)}\\n`;
                            srtContent += `${seg.text}\\n\\n`;
                        });
                        subtitlePreview.textContent = srtContent;
                        subtitlePreviewArea.style.display = 'block';
                    } else {
                        subtitlePreviewArea.style.display = 'none';
                    }
                    
                    // 设置下载链接
                    const audioLink = document.getElementById('audioDownload');
                    const srtLink = document.getElementById('srtDownload');
                    
                    audioLink.href = data.audio_url;
                    audioLink.download = data.audio_url.split('/').pop();
                    
                    if (data.srt_url) {
                        srtLink.href = data.srt_url;
                        srtLink.download = data.srt_url.split('/').pop();
                        srtLink.style.display = 'inline-flex';
                    } else {
                        srtLink.style.display = 'none';
                    }
                    
                    // 保存数据，显示达芬奇按钮
                    window.lastAudioFile = data.audio_url.split('/').pop();
                    window.lastSrtFile = data.srt_url ? data.srt_url.split('/').pop() : null;
                    window.lastJsonFile = data.json_url ? data.json_url.split('/').pop() : null;
                    window.lastSegments = data.segments || [];
                    document.getElementById('davinciBtn').style.display = 'inline-flex';
                }
            } catch(e) {
                showMsg(msgDiv, '生成失败: ' + e, false);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '生成语音';
            }
        }
        
        function formatSrtTime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            const ms = Math.floor((seconds % 1) * 1000);
            return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
        }

        function onModelChange() {
            const model = document.getElementById('modelSelect').value;
            const tip = document.querySelector('.tip');
            const promptType = document.getElementById('promptType');
            
            // 根据模型自动切换提示词类型
            if (model === 'moss') {
                tip.innerHTML = 'MOSS-TTSD 专为长文本设计，支持双人对话 [S1] [S2]';
                promptType.value = 'moss';
            } else if (model === 'indextts2') {
                tip.innerHTML = 'IndexTTS-2 零样本语音克隆，情感表达自然';
                promptType.value = 'indextts2';
            } else {  // cosyvoice
                tip.innerHTML = '支持情感控制：用开心的语气说&lt;|endofprompt|&gt;今天真开心！';
                promptType.value = 'cosyvoice';
            }
            
            // 切换提示词内容
            switchPromptType();
            
            // 更新音色列表（显示对应模型的音色）
            updateVoiceList();
        }

        async function deleteVoice() {
            const uri = document.getElementById('delSelect').value;
            const msgDiv = document.getElementById('delMsg');
            if (!uri) { showMsg(msgDiv, '请选择要删除的声音', false); return; }
            if (!confirm('确定删除吗？将从服务器永久删除！')) return;

            try {
                const res = await fetch('/api/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ uri })
                });
                const data = await res.json();
                showMsg(msgDiv, data.message, data.success);
                if (data.success) loadVoices();
            } catch(e) {
                showMsg(msgDiv, '删除失败: ' + e, false);
            }
        }

        function showMsg(div, msg, success) {
            div.textContent = msg;
            div.className = 'message show ' + (success ? 'success' : 'error');
        }

        function updateFileName() {
            const file = document.getElementById('refAudio').files[0];
            const div = document.getElementById('fileName');
            div.textContent = file ? '✅ ' + file.name : '';
        }

        // 保存光标位置
        let lastCursorPos = 0;
        document.getElementById('ttsText').addEventListener('blur', function() {
            lastCursorPos = this.selectionStart;
        });
        document.getElementById('ttsText').addEventListener('keyup', function() {
            lastCursorPos = this.selectionStart;
        });
        document.getElementById('ttsText').addEventListener('click', function() {
            lastCursorPos = this.selectionStart;
        });

        function insertTag(tag) {
            const textarea = document.getElementById('ttsText');
            const text = textarea.value;
            // 使用保存的光标位置
            const pos = lastCursorPos;
            textarea.value = text.substring(0, pos) + tag + text.substring(pos);
            textarea.focus();
            const newPos = pos + tag.length;
            textarea.selectionStart = textarea.selectionEnd = newPos;
            lastCursorPos = newPos;
        }

        function insertAtStart(tag) {
            const textarea = document.getElementById('ttsText');
            // 情感指令只能放开头，先清除已有的指令
            let text = textarea.value;
            // 移除开头已有的指令（xxx<|endofprompt|>格式）
            text = text.replace(/^[^<]*<\|endofprompt\|>/, '');
            textarea.value = tag + text;
            textarea.focus();
            lastCursorPos = tag.length;
        }

        async function aiOptimizeText() {
            const text = document.getElementById('ttsText').value.trim();
            const model = document.getElementById('modelSelect').value;
            const systemPrompt = document.getElementById('systemPrompt').value;
            const btn = document.getElementById('aiOptBtn');
            const msgDiv = document.getElementById('genMsg');

            if (!text) { showMsg(msgDiv, '请先输入文字', false); return; }
            if (!systemPrompt) { showMsg(msgDiv, '请填写AI优化提示词', false); return; }

            btn.disabled = true;
            btn.innerHTML = 'AI优化中... <span class="spinner"></span>';

            try {
                const res = await fetch('/api/ai_optimize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, model, system_prompt: systemPrompt })
                });
                const data = await res.json();
                if (data.success) {
                    document.getElementById('ttsText').value = data.optimized_text;
                    showMsg(msgDiv, '✅ AI优化完成', true);
                } else {
                    showMsg(msgDiv, '优化失败: ' + data.message, false);
                }
            } catch(e) {
                showMsg(msgDiv, '请求失败: ' + e, false);
            } finally {
                btn.disabled = false;
                btn.innerHTML = 'AI优化';
            }
        }

        // 导入到达芬奇 - 音频+字幕一起导入并对齐
        async function importToDavinci() {
            const btn = document.getElementById('davinciBtn');
            const msgDiv = document.getElementById('genMsg');
            
            if (!window.lastAudioFile) {
                showMsg(msgDiv, '请先生成音频', false);
                return;
            }
            
            btn.disabled = true;
            btn.innerHTML = '导入中... <span class="spinner"></span>';
            
            try {
                const res = await fetch('/api/davinci/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        audio_file: window.lastAudioFile,
                        srt_file: window.lastSrtFile || null,
                        json_file: window.lastJsonFile || null,
                        segments: window.lastSegments || []
                    })
                });
                const data = await res.json();
                if (!data.success && data.message.includes('路径未配置')) {
                    showDavinciConfig();
                }
                showMsg(msgDiv, data.message, data.success);
            } catch(e) {
                showMsg(msgDiv, '导入失败: ' + e, false);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '🎬 导入达芬奇';
            }
        }
        
        // 达芬奇配置相关
        function showDavinciConfig() {
            document.getElementById('davinciConfigModal').style.display = 'flex';
            // 加载当前配置
            fetch('/api/davinci/config').then(r => r.json()).then(data => {
                if (data.configured) {
                    document.getElementById('resolveExePath').value = data.resolve_exe || '';
                }
            });
        }
        
        function hideDavinciConfig() {
            document.getElementById('davinciConfigModal').style.display = 'none';
        }
        
        async function saveDavinciConfig() {
            const path = document.getElementById('resolveExePath').value.trim();
            const msgDiv = document.getElementById('davinciConfigMsg');
            
            if (!path) {
                showMsg(msgDiv, '请输入Resolve.exe路径', false);
                return;
            }
            
            try {
                const res = await fetch('/api/davinci/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ resolve_exe: path })
                });
                const data = await res.json();
                showMsg(msgDiv, data.message, data.success);
                if (data.success) {
                    setTimeout(hideDavinciConfig, 1500);
                }
            } catch(e) {
                showMsg(msgDiv, '保存失败: ' + e, false);
            }
        }
        
        // API配置相关
        async function showApiConfig() {
            document.getElementById('apiConfigModal').style.display = 'flex';
            try {
                const res = await fetch('/api/config');
                const data = await res.json();
                if (data.success) {
                    const cfg = data.config;
                    document.getElementById('ttsApiKey').value = cfg.tts.api_key || '';
                    document.getElementById('ttsBaseUrl').value = cfg.tts.base_url || '';
                    document.getElementById('ttsModel').value = cfg.tts.model || '';
                    document.getElementById('llmSplitApiKey').value = cfg.llm_split.api_key || '';
                    document.getElementById('llmSplitBaseUrl').value = cfg.llm_split.base_url || '';
                    document.getElementById('llmSplitModel').value = cfg.llm_split.model || '';
                    document.getElementById('llmOptApiKey').value = cfg.llm_optimize.api_key || '';
                    document.getElementById('llmOptBaseUrl').value = cfg.llm_optimize.base_url || '';
                    document.getElementById('llmOptModel').value = cfg.llm_optimize.model || '';
                }
            } catch(e) {
                console.error('加载配置失败:', e);
            }
        }
        
        function hideApiConfig() {
            document.getElementById('apiConfigModal').style.display = 'none';
        }
        
        async function saveApiConfig() {
            const msgDiv = document.getElementById('apiConfigMsg');
            const config = {
                tts: {
                    api_key: document.getElementById('ttsApiKey').value.trim(),
                    base_url: document.getElementById('ttsBaseUrl').value.trim(),
                    model: document.getElementById('ttsModel').value.trim()
                },
                llm_split: {
                    api_key: document.getElementById('llmSplitApiKey').value.trim(),
                    base_url: document.getElementById('llmSplitBaseUrl').value.trim(),
                    model: document.getElementById('llmSplitModel').value.trim()
                },
                llm_optimize: {
                    api_key: document.getElementById('llmOptApiKey').value.trim(),
                    base_url: document.getElementById('llmOptBaseUrl').value.trim(),
                    model: document.getElementById('llmOptModel').value.trim()
                }
            };
            
            try {
                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                const data = await res.json();
                showMsg(msgDiv, data.message, data.success);
                if (data.success) {
                    setTimeout(hideApiConfig, 1500);
                }
            } catch(e) {
                showMsg(msgDiv, '保存失败: ' + e, false);
            }
        }
        
        // ============ STT 语音识别功能 ============
        function showSTTModal() {
            document.getElementById('sttModal').style.display = 'flex';
            document.getElementById('sttResult').style.display = 'none';
            document.getElementById('sttResultText').value = '';
            document.getElementById('sttInsertBtn').style.display = 'none';
            document.getElementById('sttDownloadBtn').style.display = 'none';
            document.getElementById('sttAudioFile').value = '';
            hideMsg(document.getElementById('sttMsg'));
            window.sttSegments = null; // 清除之前的字幕数据
        }
        
        function hideSTTModal() {
            document.getElementById('sttModal').style.display = 'none';
        }
        
        async function recognizeAudio() {
            const fileInput = document.getElementById('sttAudioFile');
            const btn = document.getElementById('sttRecognizeBtn');
            const msgDiv = document.getElementById('sttMsg');
            
            if (!fileInput.files || !fileInput.files[0]) {
                showMsg(msgDiv, '请先选择音频文件', false);
                return;
            }
            
            const file = fileInput.files[0];
            const fileSizeMB = (file.size / 1024 / 1024).toFixed(2);
            
            const formData = new FormData();
            formData.append('audio', file);
            
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> 识别中...';
            
            // 显示提示 - 大文件需要更长时间
            if (file.size > 1 * 1024 * 1024) {
                showMsg(msgDiv, `文件 ${fileSizeMB} MB，识别中，请耐心等待（可能需要1-2分钟）...`, true);
            } else {
                hideMsg(msgDiv);
            }
            
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 120000); // 120秒超时
                
                const res = await fetch('/api/stt', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                const data = await res.json();
                
                if (data.success) {
                    document.getElementById('sttResultText').value = data.text;
                    document.getElementById('sttResult').style.display = 'block';
                    document.getElementById('sttInsertBtn').style.display = 'inline-flex';
                    document.getElementById('sttDownloadBtn').style.display = 'inline-flex';
                    window.sttSegments = data.segments; // 保存字幕数据
                    showMsg(msgDiv, `识别成功！语言: ${data.language || '未知'}, 时长: ${data.duration ? data.duration.toFixed(1) + '秒' : '未知'}`, true);
                } else {
                    showMsg(msgDiv, data.message || '识别失败', false);
                }
            } catch(e) {
                if (e.name === 'AbortError') {
                    showMsg(msgDiv, '识别超时（超过2分钟），请使用较短的音频文件', false);
                } else {
                    showMsg(msgDiv, '识别失败: ' + e, false);
                }
            } finally {
                btn.disabled = false;
                btn.innerHTML = '开始识别';
            }
        }
        
        function insertSTTResult() {
            const text = document.getElementById('sttResultText').value;
            if (text) {
                document.getElementById('ttsText').value = text;
                hideSTTModal();
            }
        }
        
        function downloadSTTSubtitle() {
            if (!window.sttSegments || window.sttSegments.length === 0) {
                alert('没有字幕数据');
                return;
            }
            
            // 生成 SRT 格式字幕
            let srt = '';
            window.sttSegments.forEach((seg, index) => {
                const startTime = formatSRTTime(seg.start);
                const endTime = formatSRTTime(seg.end);
                srt += `${index + 1}\n${startTime} --> ${endTime}\n${seg.text}\n\n`;
            });
            
            // 下载文件
            const blob = new Blob([srt], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `字幕_${new Date().getTime()}.srt`;
            a.click();
            URL.revokeObjectURL(url);
        }
        
        function formatSRTTime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            const ms = Math.floor((seconds % 1) * 1000);
            return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
        }
        
        // 页面加载时自动加载声音列表
        console.log('[DEBUG] 脚本开始执行...');
        
        window.addEventListener('DOMContentLoaded', function() {
            console.log('[DEBUG] DOMContentLoaded 事件触发！');
            console.log('[DEBUG] 页面加载完成，开始加载声音...');
            loadVoices();
        });
        
        // 备用：如果 DOMContentLoaded 已经触发过了，直接加载
        if (document.readyState === 'loading') {
            console.log('[DEBUG] 文档正在加载中，等待 DOMContentLoaded...');
        } else {
            console.log('[DEBUG] 文档已加载完成，立即加载声音...');
            loadVoices();
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/voices')
def api_voices():
    """获取所有声音（从服务器获取），按模型分类"""
    try:
        server_voices = get_server_voices()
        all_clones = server_voices.get("result", [])
        
        # 按模型分类音色
        cosyvoice_clones = []
        indextts2_clones = []
        
        for voice in all_clones:
            uri = voice.get('uri', '')
            # 根据 customName 判断模型（上传时的命名规则）
            custom_name = voice.get('customName', '')
            
            # IndexTTS-2 的音色包含 "index" 关键字
            if 'index' in custom_name.lower():
                indextts2_clones.append(voice)
            else:
                # 默认是 CosyVoice2
                cosyvoice_clones.append(voice)
        
        return jsonify({
            "clones": cosyvoice_clones,  # CosyVoice2 音色
            "indextts2_clones": indextts2_clones,  # IndexTTS-2 音色
            "presets": PRESETS
        })
    except Exception as e:
        print(f"[ERROR] /api/voices: {e}")
        return jsonify({"clones": [], "indextts2_clones": [], "presets": PRESETS})

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """上传音频到SiliconFlow服务器"""
    try:
        file = request.files.get('audio')
        name = request.form.get('name', '').strip()
        ref_text = request.form.get('text', '').strip()
        model_type = request.form.get('model', 'cosyvoice').strip()  # 获取模型类型
        
        if not file:
            return jsonify({"success": False, "message": "请上传音频文件"})
        if not name:
            return jsonify({"success": False, "message": "请输入声音名称"})
        if not ref_text:
            return jsonify({"success": False, "message": "请输入参考音频中说的话"})
        
        # 根据模型类型设置模型名称
        if model_type == 'indextts2':
            tts_model = 'IndexTeam/IndexTTS-2'
        else:  # cosyvoice 或 moss（都用 CosyVoice2）
            tts_model = 'FunAudioLLM/CosyVoice2-0.5B'
        
        # 保存临时文件
        temp_path = BASE_DIR / f"_temp_{name}{Path(file.filename).suffix}"
        file.save(str(temp_path))
        
        # 上传到服务器，指定模型
        print(f"[INFO] 上传声音到服务器: {name}，模型: {tts_model}")
        success, uri, result = upload_voice_to_server(str(temp_path), name, ref_text, tts_model)
        
        # 删除临时文件
        if temp_path.exists():
            os.remove(temp_path)
        
        if success and uri:
            print(f"[INFO] 上传成功: {uri}")
            return jsonify({"success": True, "message": f"✅ 上传成功！URI: {uri[:50]}...", "uri": uri})
        else:
            print(f"[ERROR] 上传失败: {result}")
            return jsonify({"success": False, "message": f"上传失败: {result}"})
    except Exception as e:
        print(f"[ERROR] /api/upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"上传失败: {e}"})

def split_text_by_sentences(text, max_chars=30):
    """按短句分割文本，每条字幕最多30个字
    
    分割规则：
    1. 先按句号、问号、感叹号分成大句
    2. 大句内按逗号、顿号、分号分成小句
    3. 合并小句直到接近30字
    4. 超过30字的强制分割
    """
    import re
    # 去除空格
    text = text.replace(' ', '').replace('　', '')
    
    # 先按句末标点分割成大句
    sentences = re.split(r'([。！？])', text)
    
    result = []
    
    for i in range(0, len(sentences), 2):
        sentence = sentences[i] if i < len(sentences) else ""
        end_punct = sentences[i+1] if i+1 < len(sentences) else ""
        full_sentence = sentence + end_punct
        
        if not full_sentence.strip():
            continue
        
        # 如果整句 <= 30字，直接用
        if len(full_sentence) <= max_chars:
            result.append(full_sentence)
            continue
        
        # 句子太长，按逗号等分割
        parts = re.split(r'([，、；：])', full_sentence)
        current = ""
        
        for j in range(0, len(parts), 2):
            part = parts[j] if j < len(parts) else ""
            punct = parts[j+1] if j+1 < len(parts) else ""
            segment = part + punct
            
            if not segment.strip():
                continue
            
            # 如果当前累积+新片段 <= 30字，合并
            if len(current) + len(segment) <= max_chars:
                current += segment
            else:
                # 保存当前，开始新的
                if current:
                    result.append(current)
                # 如果单个片段就超过30字，强制分割
                if len(segment) > max_chars:
                    for k in range(0, len(segment), max_chars):
                        chunk = segment[k:k+max_chars]
                        if chunk:
                            result.append(chunk)
                    current = ""
                else:
                    current = segment
        
        if current:
            result.append(current)
    
    return result if result else [text]

def clean_text_for_subtitle(text):
    """清理TTS标记，只保留纯文本用于字幕显示"""
    import re
    
    # 1. 清理情感/方言指令（xxx<|endofprompt|> 格式，整个删除）
    # 例如：用四川话说<|endofprompt|>正文 -> 正文
    # 注意：指令可能在开头或中间（AI优化后可能插入）
    text = re.sub(r'[^<\n]*<\|endofprompt\|>', '', text)
    
    # 2. 清理所有方括号标签 [breath] [sigh] [laughter] [mn] [cough] [noise] [quick_breath] [lipsmack] 等
    text = re.sub(r'\[[a-zA-Z_-]+\]', '', text)
    
    # 3. 清理XML风格标签 <strong> </strong> <laughter> </laughter> 等
    text = re.sub(r'</?strong>', '', text)
    text = re.sub(r'</?laughter>', '', text)
    text = re.sub(r'</?[a-zA-Z]+>', '', text)  # 清理所有HTML标签
    
    # 4. 清理可能残留的特殊标记
    text = re.sub(r'<\|[^|]+\|>', '', text)  # 清理所有 <|xxx|> 格式
    
    # 5. 清理多余空格和特殊字符
    text = re.sub(r'\s+', '', text)
    text = text.replace('　', '').replace('\u3000', '')
    
    return text.strip()

def ai_split_text(text, max_chars=15):
    """用AI智能分割文本，确保语义完整、符合说话节奏"""
    import re
    
    # 先清理TTS标记，这些不应该显示在字幕里
    clean_text = clean_text_for_subtitle(text)
    
    # 获取LLM分割配置
    config = get_config()
    llm_config = config['llm_split']
    api_key = llm_config.get('api_key') or config['tts'].get('api_key') or LEGACY_CONFIG.get('siliconflow_api_key', '')
    base_url = llm_config.get('base_url', 'https://api.siliconflow.cn/v1')
    model = llm_config.get('model', 'tencent/Hunyuan-A13B-Instruct')
    
    # 获取用户保存的提示词，如果没有则使用默认提示词
    saved_prompt = config.get('prompts', {}).get('split', '')
    
    if saved_prompt:
        # 使用用户保存的提示词
        system_prompt = "你是专业视频剪辑师，擅长字幕分割。直接输出分割结果，不要解释。"
        user_prompt = saved_prompt + f"\n\n文本：{clean_text}"
    else:
        # 使用默认提示词
        system_prompt = "你是专业视频剪辑师，擅长字幕分割。直接输出分割结果，不要解释。"
        user_prompt = f"""你是专业的视频后期剪辑师，精通字幕制作。请将文本分割成适合视频字幕的短句。

【你的专业视角】
- 字幕是观众阅读的，要符合阅读节奏
- 每句话要有完整的意思，让观众一眼看懂
- 重要的词汇可以单独成句，增强表达力度

【分割规则】
1. 每句最多{max_chars}个字
2. 在自然停顿处分割：句号、逗号、语气词后
3. 保持词语完整，不拆分词组
4. 重点词汇（如关键名词、动作）可以单独一句

【输出】
每行一句，不加序号

文本：{clean_text}"""
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 2000
        }
        
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
            proxies={"http": None, "https": None}
        )
        
        if resp.status_code == 200:
            result = resp.json()
            content = result['choices'][0]['message']['content'].strip()
            # 清理可能的markdown格式
            if content.startswith('```'):
                lines = content.split('\n')
                content = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])
            lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
            if lines:
                print(f"[INFO] AI分割成功: {len(lines)}段")
                return lines
    except Exception as e:
        print(f"[WARN] AI分割失败，使用规则分割: {e}")
    
    return split_text_by_sentences(clean_text, max_chars)

def merge_mp3_files(file_paths, output_path):
    """合并多个MP3文件"""
    with open(output_path, 'wb') as outfile:
        for fpath in file_paths:
            with open(fpath, 'rb') as infile:
                outfile.write(infile.read())

def get_mp3_duration(file_path):
    """获取MP3文件时长（秒）"""
    try:
        from mutagen.mp3 import MP3
        audio = MP3(file_path)
        return audio.info.length
    except:
        # 备用方案：根据文件大小估算（假设128kbps）
        file_size = os.path.getsize(file_path)
        return file_size / (128 * 1024 / 8)

def generate_srt(segments_info, output_path):
    """生成SRT字幕文件
    segments_info: [{"text": "文本", "start": 0.0, "end": 2.5}, ...]
    """
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments_info, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")
    
    print(f"[INFO] SRT字幕已生成: {output_path}")

@app.route('/api/tts', methods=['POST'])
def api_tts():
    """文字转语音 - 一次性生成音频，用Whisper识别精确时间戳"""
    try:
        data = request.json
        text = data.get('text', '').strip()
        voice_type = data.get('voice_type', '')
        voice_value = data.get('voice_value', '')
        speed = float(data.get('speed', 1.0))
        model_type = data.get('model', 'cosyvoice')
        
        if not text:
            return jsonify({"success": False, "message": "请输入文字"})
        if not voice_value:
            return jsonify({"success": False, "message": "请选择声音"})
        
        # 去除空格
        text = text.replace(' ', '').replace('　', '')
        
        # 获取TTS配置
        config = get_config()
        tts_config = config['tts']
        api_key = tts_config.get('api_key') or LEGACY_CONFIG.get('siliconflow_api_key', '')
        base_url = tts_config.get('base_url', 'https://api.siliconflow.cn/v1')
        
        # 根据用户选择的模型类型，设置对应的模型名称
        if model_type == 'moss':
            tts_model = 'fnlp/MOSS-TTSD-v0.5'
        elif model_type == 'indextts2':
            tts_model = 'IndexTeam/IndexTTS-2'
            print("[INFO] 使用 IndexTTS-2 模型")
        else:  # cosyvoice
            tts_model = 'FunAudioLLM/CosyVoice2-0.5B'
        
        print(f"[INFO] 使用模型: {tts_model}")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 根据类型设置voice参数
        if voice_type == "preset":
            voice = f"{tts_model}:{voice_value}"
        else:
            voice = voice_value
        
        # ========== 第1步：一次性生成完整音频 ==========
        print(f"[INFO] 生成音频: {text[:50]}...")
        
        # 所有模型统一使用 voice 参数（IndexTTS-2 也支持！）
        payload = {
            "model": tts_model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
            "sample_rate": 32000,
            "speed": speed,
            "max_tokens": 2048
        }
        
        print(f"[DEBUG] Payload: model={payload['model']}, voice={payload['voice'][:50]}...")
        
        resp = requests.post(
            f"{base_url}/audio/speech",
            headers=headers,
            json=payload,
            timeout=180,
            proxies={"http": None, "https": None}
        )
        
        if resp.status_code != 200:
            return jsonify({"success": False, "message": f"TTS错误: {resp.text[:200]}"})
        
        # 保存音频
        timestamp = int(time.time())
        out_name = f"tts_{timestamp}.mp3"
        out_path = OUTPUT_DIR / out_name
        with open(out_path, 'wb') as f:
            f.write(resp.content)
        print(f"[INFO] 音频已保存: {out_path}")
        
        # ========== 第2步：用AI分割原文 + Whisper获取时间戳 ==========
        max_chars = TOOL_CONFIG.get('max_subtitle_chars', 15)
        
        # 先用AI智能分割原文（保证文字正确）
        text_segments = ai_split_text(text, max_chars)
        print(f"[INFO] 文本分割: {len(text_segments)}段")
        
        # 用Whisper获取时间戳
        print("[INFO] 调用Whisper获取时间戳...")
        whisper_timestamps = whisper_get_timestamps(str(out_path))
        
        # 合并：原文 + 时间戳
        if whisper_timestamps and len(whisper_timestamps) > 0:
            # 用Whisper的时间戳分配给原文段落
            segments_info = align_text_with_timestamps(text_segments, whisper_timestamps)
        else:
            # Whisper失败，按字数比例估算时间
            print("[WARN] Whisper失败，使用估算时间")
            duration = get_mp3_duration(str(out_path))
            total_chars = sum(len(s) for s in text_segments)
            current_time = 0.0
            segments_info = []
            for seg in text_segments:
                seg_duration = (len(seg) / total_chars) * duration if total_chars > 0 else duration / len(text_segments)
                segments_info.append({
                    "text": seg,
                    "start": current_time,
                    "end": current_time + seg_duration
                })
                current_time += seg_duration
        
        # ========== 第3步：生成字幕文件 ==========
        srt_name = f"tts_{timestamp}.srt"
        srt_path = OUTPUT_DIR / srt_name
        json_name = f"tts_{timestamp}.json"
        json_path = OUTPUT_DIR / json_name
        
        if segments_info:
            generate_srt(segments_info, str(srt_path))
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({"segments": segments_info}, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] 生成成功: {out_path} (共{len(segments_info)}段字幕)")
        return jsonify({
            "success": True, 
            "message": f"✅ 生成成功！(共{len(segments_info)}段字幕)", 
            "audio_url": f"/audio/{out_name}",
            "srt_url": f"/audio/{srt_name}" if segments_info else None,
            "json_url": f"/audio/{json_name}" if segments_info else None,
            "segments": segments_info
        })
    except Exception as e:
        print(f"[ERROR] /api/tts: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"生成失败: {e}"})

def whisper_transcribe(audio_path):
    """用本地faster-whisper识别音频，返回带时间戳的字幕段落"""
    try:
        from faster_whisper import WhisperModel
        
        max_chars = TOOL_CONFIG.get('max_subtitle_chars', 15)
        
        # 模型下载到项目目录，不是C盘
        model_dir = BASE_DIR / "models"
        model_dir.mkdir(exist_ok=True)
        
        # 检查本地模型是否存在
        local_model_path = model_dir / "faster-whisper-small"
        
        print("[INFO] 加载Whisper模型...")
        if local_model_path.exists() and (local_model_path / "model.bin").exists():
            # 使用本地下载的模型
            model = WhisperModel(
                str(local_model_path),
                device="cpu",
                compute_type="int8"
            )
        else:
            # 自动下载（需要网络）
            model = WhisperModel(
                "small",
                device="cpu",
                compute_type="int8",
                download_root=str(model_dir)
            )
        
        print(f"[INFO] Whisper识别: {audio_path}")
        segments, info = model.transcribe(
            audio_path,
            language="zh",
            word_timestamps=True,  # 获取每个词的时间戳
            vad_filter=True  # 过滤静音
        )
        
        # 收集所有词和时间戳
        all_words = []
        for segment in segments:
            if segment.words:
                for word in segment.words:
                    all_words.append({
                        "word": word.word,
                        "start": word.start,
                        "end": word.end
                    })
        
        if not all_words:
            print("[WARN] Whisper没有识别到词")
            return None
        
        # 合并词为字幕段落，每段不超过max_chars
        final_segments = merge_words_to_segments(all_words, max_chars)
        
        print(f"[INFO] Whisper识别成功: {len(final_segments)}段")
        return final_segments
        
    except ImportError:
        print("[ERROR] 请安装faster-whisper: pip install faster-whisper")
        return None
    except Exception as e:
        print(f"[ERROR] Whisper识别失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def whisper_get_timestamps(audio_path):
    """用Whisper获取segment级别时间戳（更准确）"""
    try:
        model = get_whisper_model()
        if model is None:
            return None
        
        segments, info = model.transcribe(
            audio_path,
            language="zh",
            word_timestamps=False,  # 用segment级别，更稳定
            vad_filter=True
        )
        
        # 收集segment时间戳
        timestamps = []
        for segment in segments:
            timestamps.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            })
            print(f"[DEBUG] Segment: {segment.start:.2f}-{segment.end:.2f} | {segment.text.strip()[:20]}...")
        
        print(f"[INFO] Whisper获取时间戳: {len(timestamps)}个segment")
        return timestamps
        
    except Exception as e:
        print(f"[ERROR] Whisper获取时间戳失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def align_text_with_timestamps(text_segments, timestamps):
    """将原文段落与Whisper segment时间戳对齐
    
    新策略：直接使用Whisper segment的时间线，按字符比例分配
    """
    if not timestamps or not text_segments:
        print("[WARN] align_text_with_timestamps: 无时间戳或文本段落")
        return None
    
    # 构建连续时间线
    total_start = timestamps[0]['start']
    total_end = timestamps[-1]['end']
    total_duration = total_end - total_start
    
    print(f"[DEBUG] 音频时间范围: {total_start:.2f}s - {total_end:.2f}s (总时长: {total_duration:.2f}s)")
    
    # 计算原文总字符数
    total_text_chars = sum(len(seg) for seg in text_segments)
    if total_text_chars == 0:
        return None
    
    print(f"[DEBUG] 原文总字符数: {total_text_chars}, 段落数: {len(text_segments)}")
    
    # 为每个文本段落分配时间（按字符比例）
    segments_info = []
    current_char_pos = 0
    
    for i, seg in enumerate(text_segments):
        seg_len = len(seg)
        if seg_len == 0:
            continue
        
        # 按字符比例计算时间
        start_ratio = current_char_pos / total_text_chars
        end_ratio = (current_char_pos + seg_len) / total_text_chars
        
        start_time = total_start + (total_duration * start_ratio)
        end_time = total_start + (total_duration * end_ratio)
        
        # 确保最小时长0.3秒
        if end_time - start_time < 0.3:
            end_time = start_time + 0.3
        
        # 确保不超过总时长
        if end_time > total_end:
            end_time = total_end
        
        segments_info.append({
            "text": seg,
            "start": round(start_time, 2),
            "end": round(end_time, 2)
        })
        
        print(f"[DEBUG] 段落{i+1}: {start_time:.2f}-{end_time:.2f} | {seg[:15]}...")
        current_char_pos += seg_len
    
    # 后处理：防止重叠，确保连续
    for i in range(1, len(segments_info)):
        if segments_info[i]['start'] < segments_info[i-1]['end']:
            # 有重叠，调整
            mid = (segments_info[i-1]['end'] + segments_info[i]['start']) / 2
            segments_info[i-1]['end'] = round(mid, 2)
            segments_info[i]['start'] = round(mid, 2)
    
    print(f"[INFO] 对齐完成: {len(segments_info)}个字幕段落")
    return segments_info

def merge_words_to_segments(words, max_chars):
    """把words合并成segments，每段不超过max_chars"""
    segments = []
    current_text = ""
    current_start = 0
    current_end = 0
    
    for word in words:
        w_text = word.get('word', '')
        w_start = word.get('start', 0)
        w_end = word.get('end', w_start)
        
        if not current_text:
            current_start = w_start
        
        # 检查合并后是否超过max_chars
        if len(current_text) + len(w_text) <= max_chars:
            current_text += w_text
            current_end = w_end
        else:
            # 保存当前段落
            if current_text:
                segments.append({"text": current_text.strip(), "start": current_start, "end": current_end})
            current_text = w_text
            current_start = w_start
            current_end = w_end
    
    # 保存最后一段
    if current_text:
        segments.append({"text": current_text.strip(), "start": current_start, "end": current_end})
    
    return segments

def split_long_segment(text, start, end, max_chars):
    """把长segment分割成多个短的"""
    duration = end - start
    parts = split_text_by_sentences(text, max_chars)
    if len(parts) <= 1:
        return [{"text": text, "start": start, "end": end}]
    
    avg_duration = duration / len(parts)
    segments = []
    current_time = start
    for part in parts:
        segments.append({
            "text": part,
            "start": current_time,
            "end": current_time + avg_duration
        })
        current_time += avg_duration
    return segments

def split_text_with_duration(text, duration, max_chars):
    """按字数分割文本，均分时长"""
    parts = split_text_by_sentences(text, max_chars)
    if not parts:
        return [{"text": text, "start": 0, "end": duration}]
    
    avg_duration = duration / len(parts)
    segments = []
    current_time = 0
    for part in parts:
        segments.append({
            "text": part,
            "start": current_time,
            "end": current_time + avg_duration
        })
        current_time += avg_duration
    return segments

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_file(OUTPUT_DIR / filename, mimetype='audio/mpeg')

@app.route('/api/delete', methods=['POST'])
def api_delete():
    """删除服务器上的预置音色"""
    try:
        uri = request.json.get('uri', '')
        if not uri:
            return jsonify({"success": False, "message": "缺少uri"})
        
        print(f"[INFO] 删除声音: {uri}")
        if delete_server_voice(uri):
            return jsonify({"success": True, "message": "✅ 已删除"})
        else:
            return jsonify({"success": False, "message": "删除失败"})
    except Exception as e:
        return jsonify({"success": False, "message": f"删除失败: {e}"})

@app.route('/api/stt', methods=['POST'])
def api_stt():
    """语音转文字 - STT识别"""
    try:
        print("[INFO] STT API 被调用")
        
        if 'audio' not in request.files:
            print("[ERROR] 未找到音频文件")
            return jsonify({"success": False, "message": "未上传音频文件"})
        
        audio_file = request.files['audio']
        if audio_file.filename == '':
            print("[ERROR] 文件名为空")
            return jsonify({"success": False, "message": "文件名为空"})
        
        print(f"[INFO] 收到音频文件: {audio_file.filename}")
        
        # 保存临时文件 - 保持原始扩展名
        import os
        ext = os.path.splitext(audio_file.filename)[1] or '.wav'
        temp_path = OUTPUT_DIR / f"stt_temp_{int(time.time())}{ext}"
        audio_file.save(temp_path)
        print(f"[INFO] 临时文件保存到: {temp_path}")
        
        # 执行识别
        print("[INFO] 开始识别...")
        result = stt_transcribe(temp_path)
        print(f"[INFO] 识别结果: {result}")
        
        # 删除临时文件
        try:
            if temp_path.exists():
                temp_path.unlink()
                print("[INFO] 临时文件已删除")
        except Exception as e:
            print(f"[WARN] 删除临时文件失败: {e}")
        
        return jsonify(result)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] STT API 错误: {error_detail}")
        return jsonify({"success": False, "message": f"识别失败: {e}"})

# ============ 达芬奇集成 ============
DAVINCI_CONFIG_FILE = BASE_DIR / "davinci_config.json"

def load_davinci_config():
    """加载达芬奇配置"""
    if DAVINCI_CONFIG_FILE.exists():
        try:
            return json.load(open(DAVINCI_CONFIG_FILE, 'r', encoding='utf-8'))
        except:
            pass
    return {}

def save_davinci_config(config):
    """保存达芬奇配置"""
    with open(DAVINCI_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def find_davinci_paths(resolve_exe_path):
    """根据Resolve.exe路径找到API相关文件"""
    resolve_dir = os.path.dirname(resolve_exe_path)
    
    # fusionscript.dll 在 Resolve.exe 同目录
    dll_path = os.path.join(resolve_dir, 'fusionscript.dll')
    
    # Scripting API 在 ProgramData 目录
    script_api = os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 
                              'Blackmagic Design', 'DaVinci Resolve', 'Support', 'Developer', 'Scripting')
    
    return {
        'resolve_exe': resolve_exe_path,
        'resolve_dir': resolve_dir,
        'dll_path': dll_path,
        'script_api': script_api,
        'dll_exists': os.path.exists(dll_path),
        'api_exists': os.path.exists(script_api)
    }

def get_resolve():
    """连接达芬奇Resolve"""
    import sys
    
    config = load_davinci_config()
    resolve_exe = config.get('resolve_exe', '')
    
    if not resolve_exe or not os.path.exists(resolve_exe):
        print("[ERROR] 达芬奇路径未配置或不存在")
        return None
    
    paths = find_davinci_paths(resolve_exe)
    
    if not paths['dll_exists']:
        print(f"[ERROR] fusionscript.dll 不存在: {paths['dll_path']}")
        return None
    
    if not paths['api_exists']:
        print(f"[ERROR] Scripting API 不存在: {paths['script_api']}")
        return None
    
    # 设置环境变量
    os.environ['RESOLVE_SCRIPT_API'] = paths['script_api']
    os.environ['RESOLVE_SCRIPT_LIB'] = paths['dll_path']
    
    # 添加到Python路径
    modules_path = os.path.join(paths['script_api'], 'Modules')
    if modules_path not in sys.path:
        sys.path.insert(0, modules_path)
    
    try:
        import DaVinciResolveScript as dvr
        resolve = dvr.scriptapp("Resolve")
        return resolve
    except Exception as e:
        print(f"[ERROR] 连接达芬奇失败: {e}")
        return None

@app.route('/api/davinci/config', methods=['GET', 'POST'])
def api_davinci_config():
    """获取或设置达芬奇配置"""
    if request.method == 'GET':
        config = load_davinci_config()
        resolve_exe = config.get('resolve_exe', '')
        if resolve_exe and os.path.exists(resolve_exe):
            paths = find_davinci_paths(resolve_exe)
            return jsonify({
                "success": True,
                "configured": True,
                "resolve_exe": resolve_exe,
                "dll_exists": paths['dll_exists'],
                "api_exists": paths['api_exists']
            })
        return jsonify({"success": True, "configured": False})
    
    else:  # POST
        data = request.json
        resolve_exe = data.get('resolve_exe', '')
        
        if not resolve_exe:
            return jsonify({"success": False, "message": "请选择Resolve.exe文件"})
        
        if not os.path.exists(resolve_exe):
            return jsonify({"success": False, "message": f"文件不存在: {resolve_exe}"})
        
        if not resolve_exe.lower().endswith('.exe'):
            return jsonify({"success": False, "message": "请选择.exe文件"})
        
        paths = find_davinci_paths(resolve_exe)
        
        if not paths['dll_exists']:
            return jsonify({"success": False, "message": f"找不到fusionscript.dll，请确认选择的是达芬奇安装目录下的Resolve.exe"})
        
        # 保存配置
        save_davinci_config({'resolve_exe': resolve_exe})
        
        return jsonify({
            "success": True, 
            "message": "✅ 达芬奇路径配置成功！",
            "dll_exists": paths['dll_exists'],
            "api_exists": paths['api_exists']
        })

@app.route('/api/davinci/status')
def api_davinci_status():
    """检查达芬奇连接状态"""
    try:
        resolve = get_resolve()
        if resolve:
            project = resolve.GetProjectManager().GetCurrentProject()
            if project:
                timeline = project.GetCurrentTimeline()
                return jsonify({
                    "success": True,
                    "connected": True,
                    "project": project.GetName(),
                    "timeline": timeline.GetName() if timeline else "无时间线"
                })
        return jsonify({"success": False, "connected": False, "message": "达芬奇未打开或无项目"})
    except Exception as e:
        return jsonify({"success": False, "connected": False, "message": str(e)})

@app.route('/api/davinci/import', methods=['POST'])
def api_davinci_import():
    """导入音频到达芬奇时间线，使用Text+模板自动放置字幕"""
    try:
        data = request.json
        audio_file = data.get('audio_file', '')
        srt_file = data.get('srt_file', '')
        json_file = data.get('json_file', '')
        segments = data.get('segments', [])  # 直接传入的字幕段落信息
        
        if not audio_file:
            return jsonify({"success": False, "message": "缺少音频文件"})
        
        # 获取完整路径
        audio_path = str(OUTPUT_DIR / audio_file)
        if not os.path.exists(audio_path):
            return jsonify({"success": False, "message": f"音频文件不存在: {audio_file}"})
        
        # 如果没有直接传入segments，尝试从JSON文件读取
        if not segments and json_file:
            json_path = OUTPUT_DIR / json_file
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                    segments = json_data.get('segments', [])
        
        # 连接达芬奇
        resolve = get_resolve()
        if not resolve:
            return jsonify({"success": False, "message": "无法连接达芬奇，请先设置达芬奇路径并确保达芬奇已打开"})
        
        project = resolve.GetProjectManager().GetCurrentProject()
        if not project:
            return jsonify({"success": False, "message": "达芬奇没有打开项目，请先在达芬奇中打开或创建一个项目"})
        
        mediaPool = project.GetMediaPool()
        
        # 导入音频到媒体池
        print(f"[INFO] 导入音频到达芬奇: {audio_path}")
        clips = mediaPool.ImportMedia([audio_path])
        
        if not clips or len(clips) == 0:
            return jsonify({"success": False, "message": "导入媒体池失败"})
        
        audio_clip = clips[0]
        
        # 检查是否有时间线，没有就用音频创建一个
        timeline = project.GetCurrentTimeline()
        if not timeline:
            print("[INFO] 没有时间线，用音频创建新时间线")
            timeline_name = audio_file.replace('.mp3', '').replace('.wav', '')
            timeline = mediaPool.CreateTimelineFromClips(timeline_name, [audio_clip])
            if not timeline:
                return jsonify({"success": False, "message": "创建时间线失败"})
            msg_parts = ["✅ 已创建时间线并导入音频"]
            audio_start_frame = timeline.GetStartFrame()
        else:
            # 有时间线，获取当前播放头位置作为插入点
            frame_rate = float(timeline.GetSetting("timelineFrameRate"))
            # 添加到时间线末尾
            result = mediaPool.AppendToTimeline([audio_clip])
            if result:
                # 获取刚添加的音频的起始位置
                audio_items = timeline.GetItemListInTrack("audio", 1)
                if audio_items:
                    audio_start_frame = audio_items[-1].GetStart()
                else:
                    audio_start_frame = timeline.GetStartFrame()
            else:
                audio_start_frame = timeline.GetStartFrame()
            msg_parts = ["✅ 音频已导入时间线"]
        
        # 获取帧率
        frame_rate = float(timeline.GetSetting("timelineFrameRate"))
        
        # 如果有字幕段落，使用Text+模板放置字幕
        if segments:
            subtitle_result = add_text_plus_subtitles(resolve, project, timeline, mediaPool, segments, audio_start_frame, frame_rate)
            if subtitle_result['success']:
                msg_parts.append(f"字幕已放置({subtitle_result['count']}条)")
            else:
                msg_parts.append(f"字幕放置失败: {subtitle_result['message']}")
        elif srt_file:
            # 回退方案：导入SRT到媒体池
            srt_path = str(OUTPUT_DIR / srt_file)
            if os.path.exists(srt_path):
                srt_clips = mediaPool.ImportMedia([srt_path])
                if srt_clips:
                    msg_parts.append("SRT已导入媒体池(需手动拖到字幕轨)")
        
        return jsonify({
            "success": True, 
            "message": f"{' | '.join(msg_parts)} | 项目: {project.GetName()}"
        })
            
    except Exception as e:
        print(f"[ERROR] 达芬奇导入失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"导入失败: {e}"})

def add_text_plus_subtitles(resolve, project, timeline, mediaPool, segments, audio_start_frame, frame_rate):
    """使用Text+模板在时间线上放置字幕
    
    参数:
        segments: [{"text": "字幕文本", "start": 0.0, "end": 2.5}, ...]
        audio_start_frame: 音频在时间线上的起始帧
        frame_rate: 时间线帧率
    """
    try:
        # 切换到编辑页面
        resolve.OpenPage("edit")
        
        # 查找或导入Text+模板
        template_item = find_or_import_text_template(mediaPool)
        if not template_item:
            return {"success": False, "message": "找不到Text+模板", "count": 0}
        
        # 获取模板帧率
        template_fps = float(template_item.GetClipProperty().get("FPS", frame_rate))
        
        # 添加新的视频轨道用于字幕
        timeline.AddTrack("video")
        track_count = timeline.GetTrackCount("video")
        timeline.SetTrackName("video", track_count, "字幕")
        
        # 准备所有字幕片段
        clip_list = []
        for seg in segments:
            start_seconds = seg['start']
            end_seconds = seg['end']
            duration_seconds = end_seconds - start_seconds
            
            # 计算在时间线上的位置（帧）
            timeline_pos = audio_start_frame + int(start_seconds * frame_rate)
            # 计算片段时长（用模板帧率）
            clip_duration = int(duration_seconds * template_fps)
            
            clip_info = {
                "mediaPoolItem": template_item,
                "mediaType": 1,  # 视频
                "startFrame": 0,
                "endFrame": max(clip_duration, 1),
                "recordFrame": timeline_pos,
                "trackIndex": track_count
            }
            clip_list.append(clip_info)
        
        # 批量添加到时间线
        timeline_items = mediaPool.AppendToTimeline(clip_list)
        
        if not timeline_items:
            return {"success": False, "message": "添加字幕片段失败", "count": 0}
        
        # 获取字幕配置
        subtitle_config = TOOL_CONFIG.get('subtitle', {})
        # 位置：x=0.5居中，y=0.92在底部
        center_x = subtitle_config.get('center_x', 0.5)
        center_y = subtitle_config.get('center_y', 0.92)
        font_name = subtitle_config.get('font', 'Microsoft YaHei')
        font_size = subtitle_config.get('size', 0.06)
        
        # 设置每个字幕的文本、位置、字体、颜色
        success_count = 0
        for i, item in enumerate(timeline_items):
            if i >= len(segments):
                break
            try:
                comp_count = item.GetFusionCompCount()
                
                if comp_count > 0:
                    comp = item.GetFusionCompByIndex(1)
                    if comp:
                        tool = comp.FindToolByID("TextPlus")
                        if tool:
                            subtitle_text = segments[i]['text']
                            tool.SetInput("StyledText", subtitle_text)
                            tool.SetInput("Center", {1: center_x, 2: center_y})
                            tool.SetInput("Font", font_name)
                            tool.SetInput("Size", font_size)
                            
                            # 设置颜色：白色文字，黑色描边，无蓝色
                            tool.SetInput("Red1", 1.0)    # 文字颜色R
                            tool.SetInput("Green1", 1.0)  # 文字颜色G
                            tool.SetInput("Blue1", 1.0)   # 文字颜色B
                            
                            # 关闭第二层（描边）的蓝色
                            tool.SetInput("Enabled2", 1)  # 启用描边
                            tool.SetInput("Red2", 0.0)    # 描边颜色R（黑色）
                            tool.SetInput("Green2", 0.0)  # 描边颜色G
                            tool.SetInput("Blue2", 0.0)   # 描边颜色B
                            
                            item.SetClipColor("Green")
                            success_count += 1
                            print(f"[INFO] 字幕{i+1}: {subtitle_text}")
            except Exception as e:
                print(f"[WARN] 设置字幕{i+1}失败: {e}")
        
        # 刷新时间线显示
        try:
            current_tc = timeline.GetCurrentTimecode()
            timeline.SetCurrentTimecode(current_tc)
        except:
            pass
        
        return {"success": True, "message": "OK", "count": success_count}
        
    except Exception as e:
        print(f"[ERROR] 添加Text+字幕失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e), "count": 0}

def find_or_import_text_template(mediaPool):
    """查找或导入Text+模板"""
    root_folder = mediaPool.GetRootFolder()
    
    # 要搜索的模板名称（按优先级）
    template_names = ["Default Template", "subtitle-template", "Text+", "Fusion Title"]
    
    # 遍历媒体池查找模板
    def search_folder(folder):
        for clip in folder.GetClipList():
            clip_type = clip.GetClipProperty().get("Type", "")
            clip_name = clip.GetClipProperty().get("Clip Name", "")
            # 检查是否是Fusion标题类型
            if "Fusion" in clip_type or "Title" in clip_type or "Generator" in clip_type:
                if any(name.lower() in clip_name.lower() for name in template_names):
                    return clip
        # 递归搜索子文件夹
        for subfolder in folder.GetSubFolderList():
            result = search_folder(subfolder)
            if result:
                return result
        return None
    
    template = search_folder(root_folder)
    
    if not template:
        # 使用本地复制的模板
        template_path = BASE_DIR / "subtitle-template.drb"
        if template_path.exists():
            print(f"[INFO] 导入字幕模板: {template_path}")
            try:
                mediaPool.ImportFolderFromFile(str(template_path))
                # 重新搜索
                template = search_folder(root_folder)
            except Exception as e:
                print(f"[WARN] 导入模板失败: {e}")
    
    return template

@app.route('/api/ai_optimize', methods=['POST'])
def api_ai_optimize():
    """AI优化文本 - 根据内容添加语气标记"""
    try:
        data = request.json
        text = data.get('text', '').strip()
        system_prompt = data.get('system_prompt', '').strip()
        
        if not text:
            return jsonify({"success": False, "message": "请输入文字"})
        
        if not system_prompt:
            return jsonify({"success": False, "message": "请填写AI优化提示词"})

        # 获取LLM优化配置
        config = get_config()
        llm_config = config['llm_optimize']
        api_key = llm_config.get('api_key') or config['tts'].get('api_key') or LEGACY_CONFIG.get('siliconflow_api_key', '')
        base_url = llm_config.get('base_url', 'https://api.siliconflow.cn/v1')
        model = llm_config.get('model', 'Pro/zai-org/GLM-4.7')
        
        # 调用大模型API
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请优化以下文本：\n\n{text}"}
            ],
            "temperature": 0.6,
            "max_tokens": 4000
        }
        
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=180,
            proxies={"http": None, "https": None}
        )
        
        if resp.status_code != 200:
            return jsonify({"success": False, "message": f"API错误: {resp.text[:200]}"})
        
        result = resp.json()
        optimized_text = result['choices'][0]['message']['content'].strip()
        
        # 清理可能的markdown格式
        if optimized_text.startswith('```'):
            lines = optimized_text.split('\n')
            optimized_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
        
        # 清理空格（SiliconFlow API要求：输入内容不要加空格）
        optimized_text = optimized_text.replace(' ', '').replace('　', '').replace('\u3000', '')
        
        print(f"[INFO] AI优化完成: {text[:30]}... -> {optimized_text[:50]}...")
        return jsonify({"success": True, "optimized_text": optimized_text})
        
    except Exception as e:
        print(f"[ERROR] /api/ai_optimize: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"优化失败: {e}"})

# ============ 提示词API ============
@app.route('/api/prompts', methods=['GET'])
def get_prompts():
    """获取保存的提示词和配置信息"""
    config = get_config()
    prompts = config.get('prompts', {})
    # 返回配置信息，包括 llm_split 模型名称
    return jsonify({
        "success": True, 
        "prompts": prompts,
        "config": {
            "llm_split": config.get('llm_split', {}),
            "llm_optimize": config.get('llm_optimize', {})
        }
    })

@app.route('/api/prompts', methods=['POST'])
def save_prompts():
    """保存提示词"""
    try:
        data = request.json
        prompt_type = data.get('type', 'cosyvoice')
        prompt = data.get('prompt', '')
        
        config = get_config()
        if 'prompts' not in config:
            config['prompts'] = {}
        config['prompts'][prompt_type] = prompt
        save_tool_config(config)
        
        return jsonify({"success": True, "message": "已保存"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ============ 配置API ============
@app.route('/api/config', methods=['GET'])
def get_api_config():
    """获取当前配置"""
    config = get_config()
    # 隐藏API密钥的中间部分
    def mask_key(key):
        if not key or len(key) < 8:
            return key
        return key[:4] + '*' * (len(key) - 8) + key[-4:]
    
    return jsonify({
        "success": True,
        "config": {
            "tts": {
                "api_key": mask_key(config['tts'].get('api_key', '')),
                "base_url": config['tts'].get('base_url', ''),
                "model": config['tts'].get('model', '')
            },
            "llm_split": {
                "api_key": mask_key(config['llm_split'].get('api_key', '')),
                "base_url": config['llm_split'].get('base_url', ''),
                "model": config['llm_split'].get('model', '')
            },
            "llm_optimize": {
                "api_key": mask_key(config['llm_optimize'].get('api_key', '')),
                "base_url": config['llm_optimize'].get('base_url', ''),
                "model": config['llm_optimize'].get('model', '')
            }
        }
    })

@app.route('/api/config', methods=['POST'])
def save_api_config():
    """保存配置"""
    try:
        data = request.json
        config = get_config()
        
        # 更新TTS配置
        if 'tts' in data:
            if data['tts'].get('api_key') and not data['tts']['api_key'].startswith('****'):
                config['tts']['api_key'] = data['tts']['api_key']
            if data['tts'].get('base_url'):
                config['tts']['base_url'] = data['tts']['base_url']
            if data['tts'].get('model'):
                config['tts']['model'] = data['tts']['model']
        
        # 更新LLM分割配置
        if 'llm_split' in data:
            if data['llm_split'].get('api_key') and not data['llm_split']['api_key'].startswith('****'):
                config['llm_split']['api_key'] = data['llm_split']['api_key']
            if data['llm_split'].get('base_url'):
                config['llm_split']['base_url'] = data['llm_split']['base_url']
            if data['llm_split'].get('model'):
                config['llm_split']['model'] = data['llm_split']['model']
        
        # 更新LLM优化配置
        if 'llm_optimize' in data:
            if data['llm_optimize'].get('api_key') and not data['llm_optimize']['api_key'].startswith('****'):
                config['llm_optimize']['api_key'] = data['llm_optimize']['api_key']
            if data['llm_optimize'].get('base_url'):
                config['llm_optimize']['base_url'] = data['llm_optimize']['base_url']
            if data['llm_optimize'].get('model'):
                config['llm_optimize']['model'] = data['llm_optimize']['model']
        
        save_tool_config(config)
        return jsonify({"success": True, "message": "配置已保存"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {e}"})

if __name__ == "__main__":
    config = get_config()
    tts_key = config['tts'].get('api_key') or LEGACY_CONFIG.get('siliconflow_api_key', '')

    print("=" * 60)
    print("Sound Clone Tool - SiliconFlow CosyVoice2")
    print("=" * 60)
    print(f"TTS API Key: {'Configured' if tts_key else 'Not configured!'}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)
    print("Instructions:")
    print("   1. Upload 8-10 seconds of clean human voice audio")
    print("   2. You must accurately fill in what is said in the audio")
    print("   3. The audio will be uploaded to SiliconFlow server for storage")
    print("   4. Using server-side preset voices gives better and more stable results")
    print("=" * 60)
    print("Access at: http://localhost:7860")
    print("=" * 60)
    app.run(host="0.0.0.0", port=7860, debug=False)
