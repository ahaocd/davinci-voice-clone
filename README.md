<div align="center">
  <a href="https://www.xasia.cc">
    <img src="banner.png" alt="黑盒智能体 - 一键智能搭建网络专线,电商网站,智能证书" width="100%">
  </a>
  <p><b>🚀 黑盒智能体</b> - 一键智能搭建网络专线、电商网站、智能证书 | <a href="https://www.xasia.cc">www.xasia.cc</a></p>
</div>

---

# 🎬 Voice Clone Studio

DaVinci Resolve 字幕自动对齐工具，集成多模型 TTS 声音克隆和 AI 智能优化功能。

## ✨ 核心功能

- 🎬 **达芬奇字幕对齐** - 自动生成精准时间戳字幕，一键导入达芬奇
- 🎤 **多模型声音克隆** - 支持 CosyVoice2、IndexTTS-2、MOSS-TTSD 三种模型
- 🎭 **情感控制** - 支持开心、伤心、愤怒等多种情感语气
- ✨ **AI智能优化** - 自动分析文本情感和重点，智能添加标记
- 📝 **AI语义分割** - 按意群智能拆分字幕，保持语义完整
- 🌐 **繁简转换** - 自动将繁体转简体
- ⚡ **性能优化** - Whisper 模型全局缓存，速度提升 3.5 倍

## 🎯 三种 TTS 模型对比

| 模型 | 特点 | 适用场景 |
|------|------|---------|
| **CosyVoice2** | 支持细粒度标记（breath、laughter、strong） | 需要精确控制语气和停顿 |
| **IndexTTS-2** | 零样本克隆，自然度最高（MOS 4.54） | 追求最自然的语音效果 |
| **MOSS-TTSD** | 双人对话专用 | 对话场景、多角色配音 |

## 📦 快速开始

### 系统要求

- **操作系统**: Windows 10/11, Linux, macOS
- **Python**: 3.8 或更高版本
- **内存**: 最低 2GB RAM（Whisper small 模型运行需要约 1GB）
- **磁盘空间**: 最低 500MB（包含 Whisper small 模型 244MB）

### 技术栈

**后端框架**
- Flask 2.0+ - Web 服务器
- Flask-CORS - 跨域支持

**AI 模型**
- CosyVoice2 - 细粒度语音合成（支持情感标记）
- IndexTTS-2 - 零样本语音克隆（自然度最高）
- MOSS-TTSD - 双人对话专用
- Faster-Whisper - 语音识别（字幕时间戳）

**依赖库**
- requests - HTTP 请求
- mutagen - 音频元数据处理
- opencc-python-reimplemented - 繁简转换（可选）

### 一键启动

**Windows**
```bash
# 双击运行（自动安装依赖）
start.bat
```

**Linux/Mac**
```bash
# 赋予执行权限并运行
chmod +x start.sh && ./start.sh
```

启动脚本会自动：
1. ✅ 检查 Python 环境
2. ✅ 创建虚拟环境（venv）
3. ✅ 安装所有依赖
4. ✅ 创建必要目录
5. ✅ 检查 Whisper 模型
6. ✅ 启动服务器

访问: http://localhost:7860

### Whisper 模型下载

**推荐：small 模型（244MB）**

平衡速度和准确度，适合大多数场景。

**下载方式1：自动下载（首次运行）**
```bash
# 首次生成字幕时会自动下载
# 下载到: voice_clones/models/faster-whisper-small/
```

**下载方式2：手动下载（推荐国内用户）**
```bash
# 从 HuggingFace 镜像下载
https://hf-mirror.com/Systran/faster-whisper-small

# 解压到项目目录
voice_clones/models/faster-whisper-small/
├── model.bin
├── vocabulary.txt
├── config.json
└── ...
```

**模型大小对比**

| 模型 | 大小 | 速度 | 准确度 | 推荐场景 |
|------|------|------|--------|---------|
| tiny | 39MB | ⚡⚡⚡⚡⚡ | ⭐⭐ | 快速测试 |
| base | 74MB | ⚡⚡⚡⚡ | ⭐⭐⭐ | 简单场景 |
| **small** | **244MB** | **⚡⚡⚡** | **⭐⭐⭐⭐** | **推荐** |
| medium | 769MB | ⚡⚡ | ⭐⭐⭐⭐⭐ | 高准确度 |
| large | 1550MB | ⚡ | ⭐⭐⭐⭐⭐ | 专业场景 |

## ⚙️ 配置 API Key

1. 访问 [SiliconFlow](https://siliconflow.cn/) 注册获取 API Key
2. 打开 http://localhost:7860 点击 "🔑 API设置"
3. 填入 API 密钥保存

## 🎭 语气标记说明

### CosyVoice2 - 细粒度标记

**✅ 稳定标记（官方Demo验证）**

| 标记 | 说明 | 示例 |
|------|------|------|
| `[breath]` | 呼吸/停顿 | `今天天气真好，[breath]我想出去走走` |
| `[laughter]` | 笑声 | `哈哈[laughter]太好笑了` |
| `<strong>词</strong>` | 强调 | `这是<strong>重点</strong>` |
| `<laughter>文字</laughter>` | 边笑边说 | `<laughter>你太逗了</laughter>` |

**⚠️ 情感指令（只能放开头）**

```
用开心的语气说<|endofprompt|>今天真是太开心了！
用伤心的语气说<|endofprompt|>我很难过...
神秘<|endofprompt|>让我告诉你一个秘密...
快速<|endofprompt|>时间紧迫，快点！
```

### IndexTTS-2 - 自然语言情感

- ❌ 不支持细粒度标记
- ✅ 通过标点符号控制情感（！！！表达强烈情感）
- ✅ 零样本克隆，自然度最高
- ✅ 自动识别情感和重点

### MOSS-TTSD - 双人对话

- ✅ 双人对话专用模型
- ✅ 自动识别角色和情感
- ✅ 支持自然的对话节奏

## 🤖 AI 智能优化

### AI 优化提示词

点击 "AI化" 按钮，大模型会自动：
1. 分析文本的情感基调
2. 识别表达重点和关键词
3. 添加合适的语气标记（CosyVoice2）或调整标点（IndexTTS-2）
4. **保持原文内容不变，只优化标记**

### AI 语义分割

生成字幕时自动调用，大模型会：
1. 识别语义意群（如"十年运道" + "龙困井"）
2. 分析表达重点，关键词可单独成句
3. 按真人说话的自然停顿拆分
4. 每句最多 15 字，符合字幕阅读习惯

## 📄 License

MIT License

---

<div align="center">
  <h3>💬 加入交流群</h3>
  <img src="wechat-group.jpg" alt="微信交流群" width="300">
  <p>扫码加入微信交流群，获取使用帮助</p>
</div>
