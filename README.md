<div align="center">
  <a href="https://www.xasia.cc">
    <img src="banner.png" alt="黑盒智能体 - 一键智能搭建网络专线,电商网站,智能证书" width="100%">
  </a>
  <p><b>🚀 黑盒智能体</b> - 一键智能搭建网络专线、电商网站、智能证书 | <a href="https://www.xasia.cc">www.xasia.cc</a></p>
</div>

---

# 🎬 Voice Clone Studio

DaVinci Resolve 字幕自动对齐工具，集成 CosyVoice2 声音克隆和 AI 语气优化功能。

## ✨ 核心功能

- 🎬 **达芬奇字幕对齐** - 自动生成精准时间戳字幕，一键导入达芬奇
- 🎤 **声音克隆** - 上传音频样本，克隆任意声音
- 🎭 **情感控制** - 支持开心、伤心、愤怒等多种情感语气
- ✨ **AI语气优化** - 自动添加语气标记，让语音更自然生动

## 📦 快速开始

### Windows
```bash
双击运行 start.bat
```

### Linux/Mac
```bash
chmod +x start.sh && ./start.sh
```

访问: http://localhost:7860

## ⚙️ 配置 API Key

1. 访问 [SiliconFlow](https://siliconflow.cn/) 注册获取 API Key
2. 打开 http://localhost:7860 点击 "🔑 API设置"
3. 填入 API 密钥保存

## 🎭 CosyVoice2 语气标记

### ✅ 稳定标记（官方Demo验证）

| 标记 | 说明 | 示例 |
|------|------|------|
| `[breath]` | 呼吸/停顿 | `今天天气真好，[breath]我想出去走走` |
| `[laughter]` | 笑声 | `哈哈[laughter]太好笑了` |
| `<strong>词</strong>` | 强调 | `这是<strong>重点</strong>` |
| `<laughter>文字</laughter>` | 边笑边说 | `<laughter>你太逗了</laughter>` |

### ⚠️ 情感指令（只能放开头）

```
用开心的语气说<|endofprompt|>今天真是太开心了！
用伤心的语气说<|endofprompt|>我很难过...
神秘<|endofprompt|>让我告诉你一个秘密...
快速<|endofprompt|>时间紧迫，快点！
```

## 📄 License

MIT License

---

<div align="center">
  <h3>💬 加入交流群</h3>
  <img src="wechat-group.jpg" alt="微信交流群" width="300">
  <p>扫码加入微信交流群，获取使用帮助</p>
</div>
