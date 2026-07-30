from utils import parse_ais_eta


class TestParseAisEta:
    def test_valid_eta(self):
        eta = {"Month": 8, "Day": 15, "Hour": 10, "Minute": 30}
        result = parse_ais_eta(eta)
        assert result is not None
        assert "08-15T10:30" in result

    def test_none_eta(self):
        assert parse_ais_eta(None) is None

    def test_empty_dict(self):
        assert parse_ais_eta({}) is None

    def test_invalid_type(self):
        assert parse_ais_eta("string") is None

    def test_default_values_meaning_unknown(self):
        eta = {"Month": 0, "Day": 0, "Hour": 24, "Minute": 60}
        assert parse_ais_eta(eta) is None

    def test_partial_missing_keys(self):
        eta = {"Month": 8}
        assert parse_ais_eta(eta) is None

    def test_invalid_date_values(self):
        eta = {"Month": 13, "Day": 32, "Hour": 10, "Minute": 30}
        assert parse_ais_eta(eta) is None

    def test_eta_rolls_to_next_year(self, monkeypatch):
        import utils
        from datetime import datetime as real_datetime
        fake_now = real_datetime(2026, 12, 15, 0, 0)
        class FakeDatetime(real_datetime):
            @staticmethod
            def now(tz=None):
                return fake_now
        monkeypatch.setattr(utils, 'datetime', FakeDatetime)
        eta = {"Month": 1, "Day": 10, "Hour": 8, "Minute": 0}
        result = parse_ais_eta(eta)
        assert result is not None
        assert result.startswith("2027-01-10")

    def test_eta_current_year_returns_same_year(self):
        from datetime import datetime
        current_year = datetime.now().year
        eta = {"Month": 12, "Day": 25, "Hour": 0, "Minute": 0}
        result = parse_ais_eta(eta)
        assert result is not None
        assert result.startswith(str(current_year))
