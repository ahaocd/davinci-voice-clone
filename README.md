<div align="center">
  <a href="https://www.xasia.cc">
    <img src="banner.png" alt="黑盒智能体 - 一键智能搭建网络专线,电商网站,智能证书" width="100%">
  </a>
  <p><b>🚀 黑盒智能体</b> - 一键智能搭建网络专线、电商网站、智能证书 | <a href="https://www.xasia.cc">www.xasia.cc</a></p>
</div>

---

# 🎬 达芬奇字幕对齐 + 声音克隆 + AI语气优化

DaVinci Resolve 字幕自动对齐工具，集成 CosyVoice2 声音克隆和 AI 语气优化功能。

## ✨ 核心功能

- 🎬 **达芬奇字幕对齐** - 自动生成精准时间戳字幕，一键导入达芬奇
- 🎤 **声音克隆** - 上传音频样本，克隆任意声音
- 🎭 **情感控制** - 支持开心、伤心、愤怒等多种情感语气
- ✨ **AI语气优化** - 自动添加语气标记，让语音更自然生动
- ✂️ **AI智能分割** - 智能分割长文本，生成适合字幕的短句

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.8+ / Flask |
| TTS引擎 | SiliconFlow CosyVoice2 API |
| LLM | GLM-4 (可自定义) |
| 语音识别 | faster-whisper (本地) |
| 前端 | 原生HTML/CSS/JS |

## 📦 快速开始

### Windows

```bash
# 双击运行
start.bat
```

### Linux/Mac

```bash
chmod +x start.sh
./start.sh
```

### 首次运行会自动：

1. ✅ 创建Python虚拟环境
2. ✅ 安装依赖库 (flask, requests, faster-whisper, mutagen)
3. ✅ 下载Whisper模型 (~500MB，用于字幕时间戳)
4. ✅ 创建配置文件

### 访问

打开浏览器: http://localhost:7860

## ⚙️ 配置

### 获取 SiliconFlow API Key

1. 访问 [SiliconFlow](https://siliconflow.cn/)
2. 注册账号并登录
3. 在控制台获取 API Key
4. 新用户有免费额度

### 配置方式

**方式1：网页配置（推荐）**
1. 打开 http://localhost:7860
2. 点击 "🔑 API设置" 按钮
3. 填入API密钥，点击保存

**方式2：编辑配置文件**
```bash
# 编辑 voice_clones/config.json
{
  "tts": {
    "api_key": "sk-your-api-key",  // 必填
    "base_url": "https://api.siliconflow.cn/v1",
    "model": "FunAudioLLM/CosyVoice2-0.5B"
  },
  "llm_split": {
    "api_key": "",  // 留空则用TTS密钥
    "base_url": "https://api.siliconflow.cn/v1",
    "model": "Pro/zai-org/GLM-4.7"
  },
  "llm_optimize": {
    "api_key": "",  // 留空则用TTS密钥
    "base_url": "https://api.siliconflow.cn/v1", 
    "model": "Pro/zai-org/GLM-4.7"
  }
}
```

## 🎭 CosyVoice2 语气标记

### ✅ 稳定标记 (官方Demo验证)

| 标记 | 说明 | 示例 |
|------|------|------|
| `[breath]` | 呼吸/停顿 | `今天天气真好，[breath]我想出去走走` |
| `[laughter]` | 笑声 | `哈哈[laughter]太好笑了` |
| `<strong>词</strong>` | 强调 | `这是<strong>重点</strong>` |
| `<laughter>文字</laughter>` | 边笑边说 | `<laughter>你太逗了</laughter>` |

### ⚠️ 情感指令 (只能放开头)

```
用开心的语气说<|endofprompt|>今天真是太开心了！
用伤心的语气说<|endofprompt|>我很难过...
神秘<|endofprompt|>让我告诉你一个秘密...
快速<|endofprompt|>时间紧迫，快点！
```

## 📁 目录结构

```
davinci-voice-clone/
├── voice_clone_flask.py    # 主程序
├── requirements.txt        # 依赖库
├── config.example.json     # 配置模板
├── start.bat              # Windows启动脚本
├── start.sh               # Linux/Mac启动脚本
├── README.md              # 说明文档
├── LICENSE                # MIT协议
└── voice_clones/          # 数据目录 (自动创建)
    ├── config.json        # 配置文件
    ├── output/            # 输出音频
    ├── voices/            # 声音样本
    └── models/            # Whisper模型
```

## 🔧 常见问题

### Q: 首次启动很慢？
A: 首次需要下载Whisper模型(~500MB)，请耐心等待

### Q: API调用失败？
A: 检查API密钥是否正确，网络是否能访问 api.siliconflow.cn

### Q: 声音克隆效果不好？
A: 确保上传的音频：
- 时长 8-30秒
- 清晰无噪音
- 单人说话
- 准确填写音频内容

### Q: 字幕时间不准？
A: Whisper识别有一定误差，可在达芬奇中手动微调

## 📄 License

MIT License

## 🙏 致谢

- [SiliconFlow](https://siliconflow.cn/) - CosyVoice2 API
- [FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice) - CosyVoice2模型
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Whisper加速版
