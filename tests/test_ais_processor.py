import json
import pytest
from unittest.mock import MagicMock, patch

import ais_processor
from ais_processor import process_ais_message, _process_static_data, _process_position_report, init_cache_from_db


@pytest.fixture(autouse=True)
def clear_cache():
    ais_processor.ship_static_cache.clear()
    yield
    ais_processor.ship_static_cache.clear()


class TestProcessAisMessage:
    def test_position_report_calls_process_position(self, sample_position_report, mock_socketio):
        with patch('ais_processor._process_position_report') as mock:
            process_ais_message(json.dumps(sample_position_report), mock_socketio)
            mock.assert_called_once()

    def test_static_data_calls_process_static(self, sample_static_data, mock_socketio):
        with patch('ais_processor._process_static_data') as mock:
            process_ais_message(json.dumps(sample_static_data), mock_socketio)
            mock.assert_called_once()

    def test_invalid_json_does_not_raise(self, sample_invalid_message, mock_socketio):
        process_ais_message(sample_invalid_message, mock_socketio)

    def test_unknown_message_type_ignored(self, mock_socketio):
        msg = json.dumps({"MessageType": "UnknownType", "Message": {}})
        process_ais_message(msg, mock_socketio)

    def test_missing_message_type_ignored(self, mock_socketio):
        msg = json.dumps({"some_key": "value"})
        process_ais_message(msg, mock_socketio)


class TestProcessPositionReport:
    def test_saves_and_caches_position(self, mock_socketio):
        msg = {
            "Message": {
                "PositionReport": {
                    "UserID": 412345678,
                    "Latitude": 31.23,
                    "Longitude": 121.47,
                    "Cog": 180.5,
                    "Sog": 12.3
                }
            }
        }
        ais_processor.ship_static_cache[412345678] = {
            'name': 'TEST_VESSEL',
            'destination': 'SHANGHAI',
            'eta': '2026-08-15T10:30'
        }

        with patch('ais_processor.save_ship_position') as mock_save:
            _process_position_report(msg, mock_socketio, data_push_callback=None)
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            assert saved['mmsi'] == 412345678
            assert saved['lat'] == 31.23
            assert saved['ship_name'] == 'TEST_VESSEL'

    def test_invokes_data_push_callback(self, mock_socketio):
        msg = {
            "Message": {
                "PositionReport": {
                    "UserID": 412345678,
                    "Latitude": 31.0,
                    "Longitude": 121.0,
                    "Cog": 90.0,
                    "Sog": 10.0
                }
            }
        }
        callback = MagicMock()
        ais_processor.ship_static_cache[412345678] = {
            'name': 'TEST', 'destination': 'DEST', 'eta': 'ETA'
        }
        with patch('ais_processor.save_ship_position'):
            _process_position_report(msg, mock_socketio, data_push_callback=callback)
            callback.assert_called_once()
            assert callback.call_args[0][0]['mmsi'] == 412345678

    def test_missing_userid_is_ignored(self, mock_socketio):
        msg = {"Message": {"PositionReport": {"Latitude": 31.0, "Longitude": 121.0}}}
        with patch('ais_processor.save_ship_position') as mock_save:
            _process_position_report(msg, mock_socketio)
            mock_save.assert_not_called()

    def test_uses_static_cache_for_ship_info(self, mock_socketio):
        msg = {
            "Message": {
                "PositionReport": {
                    "UserID": 111111111,
                    "Latitude": 30.0,
                    "Longitude": 120.0,
                    "Cog": 45.0,
                    "Sog": 5.0
                }
            }
        }
        ais_processor.ship_static_cache[111111111] = {
            'name': 'CACHED_SHIP',
            'destination': 'CACHED_DEST',
            'eta': 'CACHED_ETA'
        }
        with patch('ais_processor.save_ship_position') as mock_save:
            _process_position_report(msg, mock_socketio)
            saved = mock_save.call_args[0][0]
            assert saved['ship_name'] == 'CACHED_SHIP'
            assert saved['destination'] == 'CACHED_DEST'
            assert saved['eta'] == 'CACHED_ETA'

    def test_falls_back_to_db_when_cache_misses(self, mock_socketio):
        msg = {
            "Message": {
                "PositionReport": {
                    "UserID": 222222222,
                    "Latitude": 30.0,
                    "Longitude": 120.0,
                    "Cog": 0,
                    "Sog": 0
                }
            }
        }
        with patch('ais_processor.get_latest_static_data_for_mmsi', return_value={
            'ship_name': 'DB_SHIP', 'destination': 'DB_DEST', 'eta': 'DB_ETA'
        }):
            with patch('ais_processor.save_ship_position') as mock_save:
                _process_position_report(msg, mock_socketio)
                saved = mock_save.call_args[0][0]
                assert saved['ship_name'] == 'DB_SHIP'
                assert saved['destination'] == 'DB_DEST'
                assert saved['eta'] == 'DB_ETA'
                assert 222222222 in ais_processor.ship_static_cache

    def test_uses_mmsi_as_name_when_no_static_data(self, mock_socketio):
        msg = {
            "Message": {
                "PositionReport": {
                    "UserID": 333333333,
                    "Latitude": 30.0,
                    "Longitude": 120.0,
                    "Cog": 0,
                    "Sog": 0
                }
            }
        }
        with patch('ais_processor.get_latest_static_data_for_mmsi', return_value=None):
            with patch('ais_processor.save_ship_position') as mock_save:
                _process_position_report(msg, mock_socketio)
                saved = mock_save.call_args[0][0]
                assert saved['ship_name'] == 333333333


class TestProcessStaticData:
    def test_saves_static_data_to_db(self, sample_static_data, mock_socketio):
        with patch('ais_processor.save_ship_static_data') as mock_save:
            _process_static_data(sample_static_data, mock_socketio)
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            assert saved['mmsi'] == 412345678
            assert saved['ship_name'] == 'TEST_VESSEL'
            assert saved['destination'] == 'SHANGHAI'

    def test_updates_cache(self, sample_static_data, mock_socketio):
        with patch('ais_processor.save_ship_static_data'):
            _process_static_data(sample_static_data, mock_socketio)
            assert 412345678 in ais_processor.ship_static_cache
            assert ais_processor.ship_static_cache[412345678]['name'] == 'TEST_VESSEL'

    def test_strips_trailing_at_signs(self, mock_socketio):
        msg = {
            "MessageType": "ShipStaticData",
            "Message": {
                "ShipStaticData": {
                    "UserID": 999,
                    "Name": "SHIP@@@@@@@",
                    "Destination": "PORT",
                    "Eta": {"Month": 1, "Day": 1, "Hour": 0, "Minute": 0}
                }
            }
        }
        with patch('ais_processor.save_ship_static_data') as mock_save:
            _process_static_data(msg, mock_socketio)
            assert mock_save.call_args[0][0]['ship_name'] == 'SHIP'

    def test_missing_userid_skipped(self, mock_socketio):
        msg = {
            "MessageType": "ShipStaticData",
            "Message": {
                "ShipStaticData": {}
            }
        }
        with patch('ais_processor.save_ship_static_data') as mock_save:
            _process_static_data(msg, mock_socketio)
            mock_save.assert_not_called()

    def test_empty_name_fills_with_default(self, mock_socketio):
        msg = {
            "MessageType": "ShipStaticData",
            "Message": {
                "ShipStaticData": {
                    "UserID": 555,
                    "Name": "",
                    "Destination": "PORT",
                    "Eta": {"Month": 1, "Day": 1, "Hour": 0, "Minute": 0}
                }
            }
        }
        with patch('ais_processor.save_ship_static_data') as mock_save:
            _process_static_data(msg, mock_socketio)
            saved = mock_save.call_args[0][0]
            assert saved['ship_name'] == 'N/A'
            assert ais_processor.ship_static_cache[555]['name'] == 555


class TestInitCacheFromDb:
    def test_populates_cache_from_db(self):
        with patch('ais_processor.get_all_ship_static_data', return_value={
            '123': {'name': 'SHIP_A', 'destination': 'DEST_A', 'eta': 'ETA_A'},
            '456': {'name': 'SHIP_B', 'destination': 'DEST_B', 'eta': 'ETA_B'}
        }):
            init_cache_from_db()
            assert len(ais_processor.ship_static_cache) == 2
            assert ais_processor.ship_static_cache['123']['name'] == 'SHIP_A'

    def test_empty_db_leaves_cache_empty(self):
        with patch('ais_processor.get_all_ship_static_data', return_value={}):
            init_cache_from_db()
            assert len(ais_processor.ship_static_cache) == 0

    def test_merges_with_existing_cache(self):
        ais_processor.ship_static_cache['999'] = {'name': 'EXISTING', 'destination': 'D', 'eta': 'E'}
        with patch('ais_processor.get_all_ship_static_data', return_value={
            '123': {'name': 'NEW', 'destination': 'D', 'eta': 'E'}
        }):
            init_cache_from_db()
            assert '999' in ais_processor.ship_static_cache
            assert '123' in ais_processor.ship_static_cache
