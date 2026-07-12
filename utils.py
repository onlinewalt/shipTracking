# utils.py
from datetime import datetime

def parse_ais_eta(eta_dict):
    """将 ShipStaticData 中的 Eta 字典转换为 ISO 格式字符串"""
    if not eta_dict or not isinstance(eta_dict, dict):
        return None
    month = eta_dict.get("Month", 0)
    day = eta_dict.get("Day", 0)
    hour = eta_dict.get("Hour", 24)
    minute = eta_dict.get("Minute", 60)
    if month == 0 or day == 0 or hour == 24 or minute == 60:
        return None
    try:
        current_year = datetime.now().year
        dt = datetime(year=current_year, month=month, day=day, hour=hour, minute=minute)
        return dt.strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return None