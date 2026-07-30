# models.py
import sqlite3
import threading
from config import Config

_db_lock = threading.Lock()

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(Config.DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn


def _with_db_lock(func):
    """装饰器：确保数据库操作在锁保护下执行"""
    def wrapper(*args, **kwargs):
        with _db_lock:
            return func(*args, **kwargs)
    return wrapper


def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. 追踪历史记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracking_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mmsi_list TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. 船舶动态位置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ship_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mmsi TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            course REAL,
            speed REAL,
            ship_name TEXT,
            destination TEXT,
            eta TEXT,
            timestamp TEXT NOT NULL
        )
    ''')

    # 3. ✅ 新增：船舶静态数据独立表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ship_static_data (
            mmsi TEXT PRIMARY KEY,
            ship_name TEXT,
            destination TEXT,
            eta TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 自动检查并添加新字段（兼容旧数据库）
    cursor.execute("PRAGMA table_info(ship_positions)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'destination' not in columns:
        cursor.execute("ALTER TABLE ship_positions ADD COLUMN destination TEXT")
        print("✅ 已自动为 ship_positions 表添加 destination 字段")
    if 'eta' not in columns:
        cursor.execute("ALTER TABLE ship_positions ADD COLUMN eta TEXT")
        print("✅ 已自动为 ship_positions 表添加 eta 字段")

    # 创建索引加速查询
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ship_positions_mmsi ON ship_positions(mmsi, timestamp)')

    conn.commit()
    conn.close()
    print("✅ SQLite 数据库初始化完成")


# ==================== 追踪历史 ====================

@_with_db_lock
def save_tracking_history(mmsi_list):
    """保存追踪历史（自动去重）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    mmsi_str = ",".join(mmsi_list)
    cursor.execute("SELECT id FROM tracking_history WHERE mmsi_list = ?", (mmsi_str,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO tracking_history (mmsi_list) VALUES (?)",
            (mmsi_str,)
        )
        conn.commit()
    conn.close()


@_with_db_lock
def get_tracking_history():
    """获取最近10条追踪历史"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT mmsi_list, created_at FROM tracking_history ORDER BY created_at DESC LIMIT 10"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ==================== 船舶位置 ====================

@_with_db_lock
def save_ship_position(data_dict):
    """保存船舶位置数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO ship_positions 
           (mmsi, lat, lon, course, speed, ship_name, destination, eta, timestamp) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data_dict['mmsi'],
            data_dict['lat'],
            data_dict['lon'],
            data_dict['course'],
            data_dict['speed'],
            data_dict.get('ship_name', ''),
            data_dict.get('destination', ''),
            data_dict.get('eta', ''),
            data_dict['timestamp']
        )
    )
    conn.commit()
    conn.close()


@_with_db_lock
def get_ship_positions(mmsi, start_time, end_time):
    """获取指定船舶在时间范围内的位置数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT lat, lon, course, speed, ship_name, destination, eta, timestamp 
           FROM ship_positions 
           WHERE mmsi = ? AND timestamp BETWEEN ? AND ? 
           ORDER BY timestamp ASC""",
        (mmsi, start_time, end_time)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@_with_db_lock
def get_latest_snapshot(ten_minutes_ago_iso, limit=1000):
    """获取全船最新快照（10分钟内）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT sp.mmsi, sp.lat, sp.lon, sp.course, sp.speed, 
               sp.ship_name, sp.destination, sp.eta, sp.timestamp
        FROM ship_positions sp
        INNER JOIN (
            SELECT mmsi, MAX(timestamp) as max_time
            FROM ship_positions
            WHERE timestamp >= ?
            GROUP BY mmsi
            LIMIT ?
        ) latest ON sp.mmsi = latest.mmsi AND sp.timestamp = latest.max_time
    """
    cursor.execute(query, (ten_minutes_ago_iso, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows


# ==================== 船舶静态数据 ====================

@_with_db_lock
def get_latest_static_data_for_mmsi(mmsi):
    """获取指定 MMSI 的最新静态数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ship_name, destination, eta FROM ship_static_data WHERE mmsi = ?",
        (mmsi,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


@_with_db_lock
def save_ship_static_data(data):
    """保存或更新船舶静态数据（UPSERT）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ship_static_data (mmsi, ship_name, destination, eta, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(mmsi) DO UPDATE SET
            ship_name = excluded.ship_name,
            destination = excluded.destination,
            eta = excluded.eta,
            updated_at = CURRENT_TIMESTAMP
    ''', (
        data['mmsi'],
        data['ship_name'],
        data['destination'],
        data['eta']
    ))
    conn.commit()
    conn.close()


@_with_db_lock
def get_all_ship_static_data():
    """获取数据库中所有船舶静态数据（用于缓存预热）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT mmsi, ship_name, destination, eta FROM ship_static_data')
    rows = cursor.fetchall()
    conn.close()

    result = {}
    for row in rows:
        result[row['mmsi']] = {
            'name': row['ship_name'],
            'destination': row['destination'],
            'eta': row['eta']
        }
    return result