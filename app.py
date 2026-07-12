# app.py
from flask import Flask, render_template
from flask_socketio import SocketIO

from config import Config
from models import init_db
from socket_events import register_socket_events
from ais_processor import init_cache_from_db

# 创建 Flask 应用
app = Flask(__name__)
app.config.from_object(Config)

# 创建 SocketIO 实例
socketio = SocketIO(app, 
                    cors_allowed_origins=Config.SOCKETIO_CORS_ALLOWED_ORIGINS, 
                    async_mode=Config.SOCKETIO_ASYNC_MODE)

# 初始化数据库
with app.app_context():
    init_db()

# 注册所有 Socket.IO 事件
register_socket_events(socketio)

# ==========================================
# 路由
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

# ==========================================
# 启动
# ==========================================

if __name__ == '__main__':

    # 初始化缓存
    init_cache_from_db()

    print("🚀 AIS 船舶追踪系统启动中...")
    print(f"📡 访问地址: http://localhost:{Config.PORT}")
    socketio.run(app, host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)