from utils.holidays import get_holidays


def test_get_holidays():
    holidays = get_holidays(2025)
    assert isinstance(holidays, list)
    assert holidays[0]['label'] == '2025-01-01'
    assert holidays[0]['value'] == 'New Year'
