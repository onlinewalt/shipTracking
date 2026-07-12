# 🚢 船舶追踪系统 / Ship Tracking System

[English](#english) | [中文](#中文)

---

<a id="english"></a>
## 🇬🇧 English

A real-time ship tracking application built with **Flask**, **Socket.IO**, and **Tianditu (TDT)** maps. The project adopts a modular architecture with strict separation between backend logic, socket event handling, and frontend assets.

### 🏗️ Project Structure

```text
.
├── app.py                  # Flask application entry point & route definitions
├── config.py               # Centralized configuration (loads .env)
├── socket_events.py        # Socket.IO event handlers & business logic
├── requirements.txt        # Python dependencies
├── models.py               # Database models 
├── ais_processor.py        # core logic for processing AIS messages
└── utils.py                # utilities
├── .env                    # Environment variables (⚠️ DO NOT commit to Git)
├── static/                 # Frontend static assets
│   ├── css/
│   │   └── style.css       # Map UI & layout styles
│   ├── js/
│   │   ├── ui.js          # Main entry & initialization
│   │   └── socket.js       # WebSocket connection & event listeners
│   └── assets/             # Icons, images, etc.
├── templates/
│   └── index.html          # Main HTML shell (loads static assets)
└── README.md
```

### ⚙️ Environment Configuration

Create a `.env` file in the root directory. **Do not hardcode sensitive keys in source code.**

```ini
# .env
# Tianditu API Key (Browser-side Key)
# ⚠️ Security Note: Configure domain whitelist in Tianditu Console!
TDT_KEY=your_tianditu_browser_key_here

# Optional: Other backend keys
API_KEY=your_other_api_key_here
```

> **💡 Security Best Practice for `TDT_KEY`:**
> 1. **Never** push `.env` to Git.
> 2. Use **Domain Whitelist** in the Tianditu Developer Console to restrict usage to `localhost` and your production domain.
> 3. The key is injected via environment variables, not hardcoded in HTML/JS.

### 🚀 Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   # Create .env file and paste your keys (see above)
   ```

3. **Run the Application**
   ```bash
   python app.py
   ```

4. **Access**
   Open <http://127.0.0.1:5000> in your browser.

### 🛠️ Tech Stack

- **Backend:** Python, Flask, Flask-SocketIO
- **Frontend:** HTML5, Vanilla JS (Modular), Tianditu GL API
- **Real-time:** WebSocket (Socket.IO)

---

<a id="中文"></a>
## 🇨🇳 中文

基于 **Flask**、**Socket.IO** 和 **天地图 (Tianditu)** 的实时船舶追踪系统。项目采用模块化架构，严格分离后端逻辑、Socket 事件处理与前端静态资源。

### 🏗️ 项目结构

```text
.
├── app.py                  # Flask 应用入口 & 路由定义
├── config.py               # 统一配置管理 (自动加载 .env)
├── socket_events.py        # Socket.IO 事件处理 & 核心业务逻辑
├── requirements.txt        # Python 依赖库
├── models.py               # 数据库模型与操作 
├── ais_processor.py        # AIS 消息处理核心逻辑
└── utils.py                # 工具函数
├── .env                    # 环境变量配置 (⚠️ 严禁提交到 Git)
├── static/                 # 前端静态资源目录
│   ├── css/
│   │   └── style.css       # 地图 UI 与布局样式
│   ├── js/
│   │   ├── ui.js          # 前端主入口 & 初始化逻辑
│   │   └── socket.js       # WebSocket 连接 & 事件监听
│   └── assets/             # 图标、图片等静态资源
├── templates/
│   └── index.html          # HTML 主骨架 (引入 static 资源)
└── README.md
```

### ⚙️ 环境变量配置

在项目根目录创建 `.env` 文件。**请勿在代码中硬编码敏感密钥。**

```ini
# .env
# 天地图 API Key (浏览器端 Key)
# ⚠️ 安全提示：请务必在天地图控制台配置域名白名单！
TDT_KEY=你的天地图浏览器端Key

# 可选：其他后端密钥
API_KEY=你的其他API密钥
```

> **💡 `TDT_KEY` 安全最佳实践：**
> 1. **绝对不要**将 `.env` 文件推送到 Git 仓库。
> 2. 登录 **天地图开发者控制台**，为浏览器端 Key 配置 **域名白名单**（仅允许 `localhost` 和你的正式域名使用）。
> 3. 密钥通过环境变量注入，而非直接写在 HTML/JS 中，便于多环境切换且更安全。

### 🚀 快速启动

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **配置环境**
   ```bash
   # 创建 .env 文件并填入你的密钥 (参考上方示例)
   ```

3. **运行应用**
   ```bash
   python app.py
   ```

4. **访问系统**
   浏览器打开 <http://127.0.0.1:5000>

### 🛠️ 技术栈

- **后端：** Python, Flask, Flask-SocketIO
- **前端：** HTML5, 原生 JS (模块化拆分), 天地图 GL API
- **实时通信：** WebSocket (Socket.IO)

---

### 📝 Notes / 注意事项

- **VS Code Users:** Ensure `python-dotenv` is installed. VS Code does not auto-inject `.env` into the Python process; `config.py` handles this via `load_dotenv()`.
- **VS Code 用户：** 确保已安装 `python-dotenv`。VS Code 不会自动将 `.env` 注入 Python 进程，`config.py` 已通过 `load_dotenv()` 处理此逻辑。
- **Frontend Assets / 前端资源：** All JS/CSS files are located in the `static/` directory. Do not place them in `templates/`.
- **前端资源：** 所有 JS/CSS 文件均位于 `static/` 目录，请勿直接放在 `templates/` 中。

---

> **🔒 Security Reminder / 安全提醒**
> Always treat API keys as secrets. Use environment variables and domain whitelisting to prevent quota abuse.
> 请始终将 API Key 视为敏感信息。使用环境变量和域名白名单防止配额被盗用。