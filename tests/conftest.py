import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ['API_KEY'] = 'test_api_key'
os.environ['TDT_KEY'] = 'test_tdt_key'


@pytest.fixture
def mock_socketio():
    sio = MagicMock()
    sio.emit = MagicMock()
    return sio


@pytest.fixture
def mock_stop_event():
    evt = MagicMock()
    evt.is_set = MagicMock(return_value=False)
    return evt


@pytest.fixture
def sample_position_report():
    return {
        "MessageType": "PositionReport",
        "Message": {
            "PositionReport": {
                "UserID": 412345678,
                "Latitude": 31.2304,
                "Longitude": 121.4737,
                "Cog": 180.5,
                "Sog": 12.3
            }
        }
    }


@pytest.fixture
def sample_static_data():
    return {
        "MessageType": "ShipStaticData",
        "Message": {
            "ShipStaticData": {
                "UserID": 412345678,
                "Name": "TEST_VESSEL@@@@@@",
                "Destination": "SHANGHAI",
                "Eta": {"Month": 8, "Day": 15, "Hour": 10, "Minute": 30}
            }
        }
    }


@pytest.fixture
def sample_invalid_message():
    return "not valid json}}}"
