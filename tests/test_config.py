import os
from config import Config


class TestConfig:
    def test_api_key_from_env(self):
        assert Config.API_KEY == 'test_api_key'

    def test_tdt_key_from_env(self):
        assert Config.TDT_KEY == 'test_tdt_key'

    def test_ais_stream_url(self):
        assert Config.AIS_STREAM_URL == 'wss://stream.aisstream.io/v0/stream'

    def test_max_retries(self):
        assert Config.MAX_RETRIES == 5

    def test_retry_delay(self):
        assert Config.RETRY_DELAY == 30

    def test_db_name(self):
        assert Config.DB_NAME == 'ships.db'

    def test_port(self):
        assert Config.PORT == 5000

    def test_flush_interval(self):
        assert Config.FLUSH_INTERVAL == 0.5

    def test_max_batch_size(self):
        assert Config.MAX_BATCH_SIZE == 150

    def test_socketio_async_mode(self):
        assert Config.SOCKETIO_ASYNC_MODE == 'threading'

    def test_socketio_cors(self):
        assert Config.SOCKETIO_CORS_ALLOWED_ORIGINS == "*"
