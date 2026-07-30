import os
import pytest
import models
from config import Config


@pytest.fixture(autouse=True)
def use_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test_ships.db"
    monkeypatch.setattr(Config, 'DB_NAME', str(db_path))
    if os.path.exists(str(db_path)):
        os.remove(str(db_path))
    models.init_db()
    yield
    if os.path.exists(str(db_path)):
        os.remove(str(db_path))


class TestInitDb:
    def test_tables_created(self):
        conn = models.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert 'tracking_history' in tables
        assert 'ship_positions' in tables
        assert 'ship_static_data' in tables
        conn.close()


class TestTrackingHistory:
    def test_save_and_get_history(self):
        mmsi_list = ["123456789", "987654321"]
        models.save_tracking_history(mmsi_list)
        history = models.get_tracking_history()
        assert len(history) >= 1
        assert "123456789,987654321" in history[0]['mmsi_list']

    def test_get_history_empty(self):
        conn = models.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tracking_history")
        conn.commit()
        conn.close()
        history = models.get_tracking_history()
        assert history == []

    def test_get_history_returns_max_10(self):
        for i in range(15):
            models.save_tracking_history([str(i)])
        history = models.get_tracking_history()
        assert len(history) == 10


class TestShipPositions:
    def test_save_and_get_positions(self):
        data = {
            'mmsi': '123456789',
            'lat': 31.23,
            'lon': 121.47,
            'course': 180.5,
            'speed': 12.3,
            'ship_name': 'TEST',
            'destination': 'SHANGHAI',
            'eta': '2026-08-15T10:30',
            'timestamp': '2026-07-30T12:00:00'
        }
        models.save_ship_position(data)

        positions = models.get_ship_positions('123456789', '2026-07-01T00:00:00', '2026-08-01T00:00:00')
        assert len(positions) == 1
        pos = positions[0]
        assert pos['lat'] == 31.23
        assert pos['lon'] == 121.47
        assert pos['course'] == 180.5
        assert pos['speed'] == 12.3
        assert pos['ship_name'] == 'TEST'
        assert pos['destination'] == 'SHANGHAI'

    def test_get_positions_empty(self):
        positions = models.get_ship_positions('999999999', '2026-01-01T00:00:00', '2026-12-31T00:00:00')
        assert positions == []

    def test_get_positions_time_filter(self):
        data = {
            'mmsi': '123456789', 'lat': 31.0, 'lon': 121.0,
            'course': 0, 'speed': 0, 'ship_name': '', 'destination': '', 'eta': '',
            'timestamp': '2026-07-01T12:00:00'
        }
        models.save_ship_position(data)
        data2 = data.copy()
        data2['timestamp'] = '2026-07-15T12:00:00'
        data2['lat'] = 32.0
        models.save_ship_position(data2)

        positions = models.get_ship_positions('123456789', '2026-07-10T00:00:00', '2026-07-20T00:00:00')
        assert len(positions) == 1
        assert positions[0]['lat'] == 32.0


class TestShipStaticData:
    def test_save_and_get_static_data(self):
        data = {
            'mmsi': '123456789',
            'ship_name': 'TEST_VESSEL',
            'destination': 'SHANGHAI',
            'eta': '2026-08-15T10:30'
        }
        models.save_ship_static_data(data)

        result = models.get_latest_static_data_for_mmsi('123456789')
        assert result is not None
        assert result['ship_name'] == 'TEST_VESSEL'
        assert result['destination'] == 'SHANGHAI'
        assert result['eta'] == '2026-08-15T10:30'

    def test_get_static_data_not_found(self):
        result = models.get_latest_static_data_for_mmsi('999999999')
        assert result is None

    def test_upsert_updates_existing(self):
        data = {
            'mmsi': '123456789', 'ship_name': 'OLD_NAME',
            'destination': 'OLD_DEST', 'eta': '2026-01-01T00:00'
        }
        models.save_ship_static_data(data)

        updated = {
            'mmsi': '123456789', 'ship_name': 'NEW_NAME',
            'destination': 'NEW_DEST', 'eta': '2026-12-31T23:59'
        }
        models.save_ship_static_data(updated)

        result = models.get_latest_static_data_for_mmsi('123456789')
        assert result['ship_name'] == 'NEW_NAME'
        assert result['destination'] == 'NEW_DEST'

    def test_get_all_static_data(self):
        models.save_ship_static_data({
            'mmsi': '111', 'ship_name': 'A', 'destination': 'D1', 'eta': 'E1'
        })
        models.save_ship_static_data({
            'mmsi': '222', 'ship_name': 'B', 'destination': 'D2', 'eta': 'E2'
        })

        all_data = models.get_all_ship_static_data()
        assert len(all_data) == 2
        assert all_data['111']['name'] == 'A'
        assert all_data['222']['name'] == 'B'


class TestLatestSnapshot:
    def test_get_latest_snapshot(self):
        models.save_ship_position({
            'mmsi': '111', 'lat': 31.0, 'lon': 121.0,
            'course': 90, 'speed': 10, 'ship_name': 'SHIP_A',
            'destination': 'DEST_A', 'eta': 'E1',
            'timestamp': '2026-07-30T12:00:00'
        })
        models.save_ship_position({
            'mmsi': '222', 'lat': 32.0, 'lon': 122.0,
            'course': 180, 'speed': 15, 'ship_name': 'SHIP_B',
            'destination': 'DEST_B', 'eta': 'E2',
            'timestamp': '2026-07-30T12:05:00'
        })

        rows = models.get_latest_snapshot('2026-07-30T11:00:00')
        assert len(rows) == 2

        mmsis = {r['mmsi'] for r in rows}
        assert '111' in mmsis
        assert '222' in mmsis

    def test_get_latest_snapshot_respects_time_window(self):
        models.save_ship_position({
            'mmsi': '111', 'lat': 31.0, 'lon': 121.0,
            'course': 0, 'speed': 0, 'ship_name': '', 'destination': '', 'eta': '',
            'timestamp': '2026-07-01T12:00:00'
        })

        rows = models.get_latest_snapshot('2026-07-30T11:00:00')
        assert len(rows) == 0

    @staticmethod
    def test_get_latest_snapshot_uses_latest_per_mmsi():
        models.save_ship_position({
            'mmsi': '111', 'lat': 10.0, 'lon': 20.0,
            'course': 0, 'speed': 0, 'ship_name': '', 'destination': '', 'eta': '',
            'timestamp': '2026-07-30T12:00:00'
        })
        models.save_ship_position({
            'mmsi': '111', 'lat': 11.0, 'lon': 21.0,
            'course': 0, 'speed': 0, 'ship_name': '', 'destination': '', 'eta': '',
            'timestamp': '2026-07-30T13:00:00'
        })

        rows = models.get_latest_snapshot('2026-07-30T11:00:00')
        assert len(rows) == 1
        assert rows[0]['lat'] == 11.0
        assert rows[0]['lon'] == 21.0
