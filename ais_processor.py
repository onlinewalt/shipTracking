# ais_processor.py
import json
import asyncio
import websockets
from datetime import datetime, timezone
from config import Config
from models import (
    save_ship_position,
    get_latest_static_data_for_mmsi,
    save_ship_static_data,
    get_all_ship_static_data
)
from utils import parse_ais_eta


# 内存缓存
ship_static_cache = {}

def init_cache_from_db():
    """从数据库中加载已有的静态船只数据到内存缓存"""
    global ship_static_cache
    db_data = get_all_ship_static_data()
    if db_data:
        ship_static_cache.update(db_data)
        print(f"✅ 缓存预热完成，已加载 {len(ship_static_cache)} 条船舶静态数据")
    else:
        print("📭 数据库中无静态数据，缓存将在运行时自动填充")

async def run_ais_client(socketio, mmsi_list, stop_event,data_push_callback=None):
    """AIS 数据流主协程"""
    retry_count = 0
    while retry_count < Config.MAX_RETRIES:
        if stop_event.is_set():
            print("✅ 收到停止信号，取消 AIS 连接尝试")
            return
        try:
            print(f"🔌 正在尝试连接 aisstream.io... (第 {retry_count + 1} 次)")
            async with websockets.connect(
                Config.AIS_STREAM_URL,
                ping_timeout=Config.SOCKETIO_PING_TIMEOUT
            ) as websocket:
                retry_count = 0
                # 构建订阅消息
                if not mmsi_list:
                    print("🌍 订阅模式：全船")
                    subscribe_message = {
                        "Apikey": Config.API_KEY,
                        "BoundingBoxes": [[[-90, -180], [90, 180]]],
                        "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
                    }
                else:
                    print(f"🎯 订阅模式：指定船只 {mmsi_list}")
                    subscribe_message = {
                        "Apikey": Config.API_KEY,
                        "BoundingBoxes": [[[-90, -180], [90, 180]]],
                        "FiltersShipMMSI": mmsi_list,
                        "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
                    }
                await websocket.send(json.dumps(subscribe_message))
                socketio.emit('status_update', {'msg': f'🚀 追踪启动: {"全船模式" if not mmsi_list else f"{len(mmsi_list)} 艘船"}'})

                async for message_json in websocket:
                    if stop_event.is_set():
                        print("🛑 收到停止信号，优雅退出 AIS 循环")
                        return
                    process_ais_message(message_json, socketio,data_push_callback)
        except Exception as e:
            if stop_event.is_set():
                print("✅ AIS 连接已正常关闭")
                return
            print(f"❌ AIS 连接/订阅失败: {e}")
            retry_count += 1
            if retry_count < Config.MAX_RETRIES:
                print(f"⏳ 将在 {Config.RETRY_DELAY} 秒后重试...")
                await asyncio.sleep(Config.RETRY_DELAY)
            else:
                socketio.emit('status_update', {'msg': f'❌ AIS 订阅失败，已重试 {Config.MAX_RETRIES} 次'})
                return

def process_ais_message(msg, socketio, data_push_callback=None):
    """处理单条 AIS 消息"""
    try:
        message = json.loads(msg)
        msg_type = message.get("MessageType")

        if msg_type == "ShipStaticData":
            _process_static_data(message, socketio)
        elif msg_type == "PositionReport":
            _process_position_report(message, socketio, data_push_callback)
    except Exception as e:
        print(f"❌ 处理 AIS 消息时发生错误: {e}")

def _process_static_data(message, socketio):
    """处理静态数据"""
    static_data = message['Message']['ShipStaticData']
    mmsi = static_data.get('UserID')
    if not mmsi: return

    name = static_data.get('Name', '').strip().strip('@')
    destination = static_data.get('Destination', '').strip()
    parsed_eta = parse_ais_eta(static_data.get('Eta'))

    # 检查数据库是否已有记录
    latest_data = get_latest_static_data_for_mmsi(mmsi)
    if latest_data and latest_data.get('ship_name'):
        # 数据库已有，更新缓存
        ship_static_cache[mmsi] = {
            'name': latest_data['ship_name'],
            'destination': destination or latest_data.get('destination', 'N/A'),
            'eta': parsed_eta or latest_data.get('eta', 'N/A')
        }
    else:
 # 数据库无记录，持久化到数据库并更新缓存
        if name:
            # ✅ 调用 models.py 中的函数将静态数据写入数据库
            save_ship_static_data({
                'mmsi': mmsi,
                'ship_name': name,
                'destination': destination or 'N/A',
                'eta': parsed_eta or 'N/A'
            })
            ship_static_cache[mmsi] = {
                'name': name,
                'destination': destination or 'N/A',
                'eta': parsed_eta or 'N/A'
            }
            print(f"📝 静态数据已持久化: MMSI={mmsi}, 船名={name}")

def _process_position_report(message, socketio, data_push_callback=None):
    """处理动态位置数据"""
    ais_message = message['Message']['PositionReport']
    mmsi = ais_message.get('UserID')
    if not mmsi: return

    # 获取静态信息
    static_info = ship_static_cache.get(mmsi)
    if not static_info:
        db_data = get_latest_static_data_for_mmsi(mmsi)
        if db_data and db_data.get('ship_name'):
            static_info = {
                'name': db_data['ship_name'],
                'destination': db_data.get('destination', 'N/A'),
                'eta': db_data.get('eta', 'N/A')
            }
            ship_static_cache[mmsi] = static_info

    ship_info = {
        'mmsi': mmsi,
        'lat': ais_message.get('Latitude'),
        'lon': ais_message.get('Longitude'),
        'course': ais_message.get('Cog', 'N/A'),
        'speed': ais_message.get('Sog', 'N/A'),
        'ship_name': static_info.get('name', mmsi) if static_info else mmsi,
        'destination': static_info.get('destination', 'N/A') if static_info else 'N/A',
        'eta': static_info.get('eta', 'N/A') if static_info else 'N/A',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    save_ship_position(ship_info)
    print(f"📍 船舶位置已保存: MMSI={mmsi}, 坐标=({ship_info['lat']}, {ship_info['lon']})")
    # 节流推送逻辑将移至 socket_events.py 中处理

        # ✅ 关键修改：使用回调函数推送数据
    if data_push_callback:
        data_push_callback(ship_info)
    # 如果 data_push_callback 为 None，则不推送（便于测试或特殊场景）