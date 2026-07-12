# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # 自动读取 .env 文件

class Config:
    # 外部服务配置
    API_KEY = os.getenv("API_KEY")
    TDT_KEY = os.getenv("TDT_KEY")
    AIS_STREAM_URL = "wss://stream.aisstream.io/v0/stream"

    # 应用配置
    MAX_RETRIES = 5
    RETRY_DELAY = 30
    DB_NAME = "ships.db"
    HOST = '0.0.0.0'
    PORT = 5000
    DEBUG = True

    # SocketIO 配置
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"
    SOCKETIO_PING_TIMEOUT = 300


    # 节流配置
    FLUSH_INTERVAL = 0.5
    MAX_BATCH_SIZE = 150