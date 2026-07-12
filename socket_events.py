import time
import threading
import asyncio
from threading import Timer
from datetime import datetime, timezone, timedelta

from flask import request
from flask_socketio import emit
import traceback

from config import Config
from models import (
    get_tracking_history, 
    get_ship_positions, 
    get_latest_snapshot, 
    save_tracking_history
)
from ais_processor import run_ais_client

# ==========================================
# 全局状态管理
# ==========================================
current_mmsi_list = []
current_mode = 'idle'  # 'idle', 'streaming'
ais_client_task = None
stop_event = threading.Event()
ais_timer = None

# ==========================================
# 节流缓冲区 (用于 batch_ship_location)
# ==========================================
throttle_buffer = {}
buffer_lock = threading.Lock()


def register_socket_events(socketio):
    """注册所有 Socket.IO 事件"""
    last_flush_time = time.time()

    # --- 内部辅助函数 ---

    def flush_buffer():
        """将缓冲区中的消息批量推送给前端"""
        nonlocal  last_flush_time
        global throttle_buffer
        with buffer_lock:
            if not throttle_buffer:
                return
            messages = list(throttle_buffer.values())
            throttle_buffer.clear()
            last_flush_time = time.time()
            
            # 分批发送，防止单包过大
            for i in range(0, len(messages), Config.MAX_BATCH_SIZE):
                batch = messages[i:i + Config.MAX_BATCH_SIZE]
                socketio.emit('batch_ship_location', {'ships': batch})
   
    def throttled_emit(msg):
        """节流入口：收到 AIS 消息时调用，只负责入队"""
        mmsi = msg.get('mmsi')
        if not mmsi: 
            print("⚠️ 收到无 MMSI 的消息，已丢弃")
            return
            
        # ✅ 3. 简化逻辑，只负责将消息放入缓冲区
        with buffer_lock:
            throttle_buffer[mmsi] = msg
            # 可选：添加调试日志
            print(f"📥 消息入队: {mmsi}, 当前缓冲区大小: {len(throttle_buffer)}")


    def start_periodic_flush():
        """启动后台线程，定时强制刷新缓冲区"""
        def periodic_flush():
            while True:
                time.sleep(Config.FLUSH_INTERVAL)
                flush_buffer()
        t = threading.Thread(target=periodic_flush, daemon=True)
        t.start()

    def stop_ais_client():
        """安全地停止 AIS 客户端"""
        global ais_client_task
        if ais_client_task and ais_client_task.is_alive():
            print("🛑 正在停止 AIS 客户端线程...")
            stop_event.set()
            ais_client_task.join(timeout=2)
            if ais_client_task.is_alive():
                print("⚠️ AIS 客户端线程未能在 2 秒内正常退出")
            ais_client_task = None
            stop_event.clear()

    def start_or_restart_ais(mmsi_list):
        """启动或重启 AIS 客户端"""
        global ais_client_task, stop_event, current_mmsi_list, current_mode

        # 1. 检查是否已有相同任务在运行
        if (ais_client_task and ais_client_task.is_alive() 
                and current_mmsi_list == mmsi_list):
            print(f"ℹ️ AIS 任务已在运行中，参数相同，跳过重启")
            return

        # 2. 停止旧任务（如果有）
        if ais_client_task and ais_client_task.is_alive():
            print("🛑 正在停止旧的 AIS 客户端线程...")
            stop_ais_client()
            ais_client_task = None

        # 3. 为新任务创建一个全新的 stop_event
        stop_event = threading.Event()

        # 4. 启动新任务
        ais_client_task = socketio.start_background_task(_ais_thread_entry, mmsi_list)
        print(f"🚀 AIS 任务已启动，参数: {mmsi_list if mmsi_list else '全船模式'}")

    def _ais_thread_entry(mmsi_list):
        """同步入口函数，用于在子线程中启动 asyncio 事件循环"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # ✅ 关键修改：将 throttled_emit 函数作为回调传入
            loop.run_until_complete(run_ais_client(socketio, mmsi_list, stop_event, throttled_emit))
        finally:
            loop.close()
            print("🧹 AIS 线程事件循环已关闭")

    def auto_stop_ais_stream():
        print("⏰ 全船模式限时已到，自动停止")
        socketio.emit('status_update', {'msg': '⏰ 全船模式限时已到，自动停止'})
        stop_event.set()

    # --- 启动定时刷新线程 ---
    start_periodic_flush()

    # ==========================================
    # Socket.IO 事件定义
    # ==========================================

    @socketio.on('connect')
    def handle_connect():
        print(f'客户端已连接: {request.sid}')

    @socketio.on('disconnect')
    def handle_disconnect():
        print(f'客户端已断开: {request.sid}')

    @socketio.on('query_ship')
    def handle_query_ship(data):
        global current_mmsi_list, current_mode, ais_timer
        
        # 取消之前的定时器
        if ais_timer:
            ais_timer.cancel()
            ais_timer = None

        raw_mmsi = data.get('mmsi', '')
        
        if not raw_mmsi.strip():
            # --- 全船模式 ---
            print("🌍 收到全船查询指令")
            current_mmsi_list = []
            current_mode = 'streaming'  # 修改：模式应为 streaming
            start_or_restart_ais(current_mmsi_list)
            
            # 设置 5 分钟自动停止
            ais_timer = Timer(300, auto_stop_ais_stream)
            ais_timer.start()
            
            emit('status_update', {'msg': '🌍 全船模式：数据采集中，5分钟后自动停止。'})
        else:
            # --- 指定船只模式 ---
            mmsi_list = [m.strip() for m in raw_mmsi.split(',') if m.strip()]
            save_tracking_history(mmsi_list)
            start_or_restart_ais(mmsi_list)
            current_mmsi_list = mmsi_list
            current_mode = 'streaming'
            
            if ais_timer:
                ais_timer.cancel()
                ais_timer = None
                
            emit('status_update', {'msg': f'🎯 正在追踪 {len(mmsi_list)} 艘船'})

    @socketio.on('all_ships_snapshot')
    def handle_get_all_ships_snapshot():
        # 修改：移除了对 current_mode 的检查，快照查询现在可以在任何模式下进行
        print("📸 收到前端快照请求，正在查询数据库...")
        emit('status_update', {'msg': '📸 正在生成全船快照...'})
        try:
            now_utc = datetime.now(timezone.utc)
            ten_minutes_ago = (now_utc - timedelta(minutes=10)).isoformat()
            
            rows = get_latest_snapshot(ten_minutes_ago)

            # 如果没有数据，返回空快照而不是报错
            if not rows:
                print("⚠️ 数据库中暂无近 10 分钟的船舶数据")
                emit('status_update', {'msg': '⚠️ 暂无数据，AIS 正在连接中，请稍后刷新'})
                socketio.emit('all_ships_snapshot', {
                    'ships': [],
                    'count': 0,
                    'time': now_utc.isoformat()
                })
                return

            ships = []
            for row in rows:
                ship_dict = {
                    'mmsi': row[0], 'lat': row[1], 'lon': row[2], 'course': row[3] or 0,
                    'speed': row[4] or 0, 'ship_name': row[5] or row[0],
                    'destination': row[6] or 'N/A', 'eta': row[7] or 'N/A', 'timestamp': row[8]
                }
                ships.append(ship_dict)
            
            socketio.emit('all_ships_snapshot', {
                'ships': ships,
                'count': len(ships),
                'time': now_utc.isoformat()
            })
            print(f"✅ 已发送全船快照，共 {len(ships)} 艘船")
        except Exception as e:
            traceback.print_exc()  # 打印完整的错误行号和调用链
            print(f"❌ 生成快照失败: {type(e).__name__}: {e}")
            emit('status_update', {'msg': f'❌ 快照生成错误: {type(e).__name__}: {e}'})

    @socketio.on('stop_tracking')
    def handle_stop_tracking():
        global current_mode, ais_timer, current_mmsi_list
        stop_event.set()
        if ais_timer:
            ais_timer.cancel()
            ais_timer = None
        current_mode = 'idle'
        current_mmsi_list = []  # 修改：重置 MMSI 列表
        print("🛑 后端收到停止指令")
        emit('status_update', {'msg': '⏹️ 追踪已停止'})

    @socketio.on('load_history')
    def handle_load_history():
        history = get_tracking_history()
        emit('history_data', {'history': history})

    @socketio.on('get_ship_track')
    def handle_get_ship_track(data):
        mmsi = data.get('mmsi')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if mmsi and start_time and end_time:
            positions = get_ship_positions(mmsi, start_time, end_time)
            if positions:
                emit('ship_track_data', {'mmsi': mmsi, 'positions': positions})
                # 强制更新状态栏显示最新位置
                latest = positions[-1]
                location_msg = {
                    'mmsi': mmsi, 'lat': latest[0], 'lon': latest[1],
                    'speed': latest[3] or 0, 'course': latest[2] or 0,
                    'ship_name': latest[4] or mmsi,
                    'destination': latest[5] or '未知',
                    'eta': latest[6] if len(latest) > 6 and latest[6] else '未知'
                }
                emit('ship_location', location_msg)
            else:
                emit('status_update', {'msg': '📭 未查询到数据'})