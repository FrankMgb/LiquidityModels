import unittest
import datetime
import pytz
from src.utils.time_utils import convert_to_et, get_market_open_close_et

class TestTimeUtils(unittest.TestCase):

    def test_convert_to_et_naive_utc_to_et(self):
        naive_utc_dt = datetime.datetime(2023, 10, 26, 14, 30) # 2:30 PM UTC
        et_dt = convert_to_et(naive_utc_dt, original_tz_str='UTC')
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.year, 2023)
        self.assertEqual(et_dt.month, 10)
        self.assertEqual(et_dt.day, 26)
        self.assertEqual(et_dt.hour, 10) # 10:30 AM EDT
        self.assertEqual(et_dt.minute, 30)
        self.assertEqual(et_dt.tzinfo.zone, 'America/New_York')
        self.assertTrue(et_dt.dst() == datetime.timedelta(hours=1)) # EDT is UTC-4

    def test_convert_to_et_naive_london_to_et(self):
        # London is UTC+1 on this date (BST)
        naive_london_dt = datetime.datetime(2023, 8, 15, 15, 30) # 3:30 PM London time
        et_dt = convert_to_et(naive_london_dt, original_tz_str='Europe/London')
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.hour, 10) # 10:30 AM EDT
        self.assertEqual(et_dt.tzinfo.zone, 'America/New_York')
        self.assertTrue(et_dt.dst() == datetime.timedelta(hours=1))

    def test_convert_to_et_aware_utc_to_et(self):
        aware_utc_dt = pytz.utc.localize(datetime.datetime(2023, 11, 5, 14, 30)) # 2:30 PM UTC
        # This is after DST change in NY (Nov 5, 2023 was the day DST ended)
        # 14:30 UTC is 9:30 AM EST (UTC-5)
        et_dt = convert_to_et(aware_utc_dt)
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.hour, 9)
        self.assertEqual(et_dt.minute, 30)
        self.assertEqual(et_dt.tzinfo.zone, 'America/New_York')
        self.assertTrue(et_dt.dst() == datetime.timedelta(0)) # EST is UTC-5

    def test_convert_to_et_naive_no_original_tz(self):
        ambiguous_naive_dt = datetime.datetime(2023, 10, 26, 10, 30)
        # Expect None because it's ambiguous without original_tz_str
        self.assertIsNone(convert_to_et(ambiguous_naive_dt))

    def test_convert_to_et_dst_fall_back_original_tz_et(self):
        # On 2023-11-05, 1:30 AM ET happens twice.
        # pytz.localize by default raises AmbiguousTimeError if is_dst is not specified.
        # Our function handles this by trying is_dst=None with localize, then normalize.
        naive_ambiguous_dt_in_et = datetime.datetime(2023, 11, 5, 1, 30, 0)
        et_dt = convert_to_et(naive_ambiguous_dt_in_et, original_tz_str='America/New_York')
        self.assertIsNotNone(et_dt) # Should resolve to one of them
        self.assertEqual(et_dt.tzinfo.zone, 'America/New_York')
        # Depending on pytz's choice for is_dst=None, it could be either the EDT or EST version.
        # Let's check it's one of the valid representations of 1:30 AM on that day in ET.
        # The first 1:30 is EDT (UTC-4), the second is EST (UTC-5).
        # So UTC times would be 5:30 or 6:30.
        utc_timestamp = et_dt.timestamp() # timestamp() gives UTC seconds
        possible_utc_1 = pytz.timezone('America/New_York').localize(datetime.datetime(2023,11,5,1,30), is_dst=True).timestamp()
        possible_utc_2 = pytz.timezone('America/New_York').localize(datetime.datetime(2023,11,5,1,30), is_dst=False).timestamp()
        self.assertTrue(utc_timestamp == possible_utc_1 or utc_timestamp == possible_utc_2)


    def test_convert_to_et_dst_spring_forward_original_tz_et(self):
        # On 2024-03-10, 2:30 AM ET does not exist due to spring forward.
        naive_non_existent_dt_in_et = datetime.datetime(2024, 3, 10, 2, 30, 0)
        # Our current simple handling in convert_to_et for NonExistentTimeError during localization returns None.
        et_dt = convert_to_et(naive_non_existent_dt_in_et, original_tz_str='America/New_York')
        self.assertIsNone(et_dt)

    def test_convert_to_et_already_et(self):
        et_tz = pytz.timezone('America/New_York')
        original_et_dt = et_tz.localize(datetime.datetime(2023, 10, 20, 10, 0, 0))
        converted_et_dt = convert_to_et(original_et_dt)
        self.assertEqual(original_et_dt, converted_et_dt)
        self.assertEqual(converted_et_dt.tzinfo.zone, 'America/New_York')


    def test_get_market_open_close_et_summer(self):
        # During EDT (UTC-4)
        trade_date_summer = datetime.date(2023, 8, 15)
        open_summer, close_summer = get_market_open_close_et(trade_date_summer)
        self.assertIsNotNone(open_summer)
        self.assertIsNotNone(close_summer)
        self.assertEqual(open_summer.hour, 9)
        self.assertEqual(open_summer.minute, 30)
        self.assertEqual(open_summer.tzinfo.zone, 'America/New_York')
        self.assertTrue(open_summer.dst() == datetime.timedelta(hours=1)) # EDT

        self.assertEqual(close_summer.hour, 16)
        self.assertEqual(close_summer.minute, 0)
        self.assertEqual(close_summer.tzinfo.zone, 'America/New_York')
        self.assertTrue(close_summer.dst() == datetime.timedelta(hours=1)) # EDT

    def test_get_market_open_close_et_winter(self):
        # During EST (UTC-5)
        trade_date_winter = datetime.date(2023, 11, 6) # Day after DST ends
        open_winter, close_winter = get_market_open_close_et(trade_date_winter)
        self.assertIsNotNone(open_winter)
        self.assertIsNotNone(close_winter)
        self.assertEqual(open_winter.hour, 9)
        self.assertEqual(open_winter.minute, 30)
        self.assertEqual(open_winter.tzinfo.zone, 'America/New_York')
        self.assertTrue(open_winter.dst() == datetime.timedelta(0)) # EST

        self.assertEqual(close_winter.hour, 16)
        self.assertEqual(close_winter.minute, 0)
        self.assertEqual(close_winter.tzinfo.zone, 'America/New_York')
        self.assertTrue(close_winter.dst() == datetime.timedelta(0)) # EST

    def test_get_market_open_close_et_custom_times(self):
        trade_date = datetime.date(2023, 10, 10)
        open_custom, close_custom = get_market_open_close_et(trade_date, open_time_str="08:00", close_time_str="14:30")
        self.assertIsNotNone(open_custom)
        self.assertIsNotNone(close_custom)
        self.assertEqual(open_custom.hour, 8)
        self.assertEqual(close_custom.hour, 14)
        self.assertEqual(close_custom.minute, 30)

    def test_get_market_open_close_et_invalid_time_str(self):
        trade_date = datetime.date(2023, 1, 1)
        open_time, close_time = get_market_open_close_et(trade_date, open_time_str="99:00")
        self.assertIsNone(open_time)
        self.assertIsNone(close_time)

    def test_get_market_open_close_on_dst_start_day(self):
        # DST starts March 10, 2024 (2 AM becomes 3 AM)
        # Market open/close times (9:30 AM, 4 PM) are well after the transition.
        dst_start_date = datetime.date(2024, 3, 10)
        open_time, close_time = get_market_open_close_et(dst_start_date)
        self.assertIsNotNone(open_time)
        self.assertEqual(open_time.hour, 9)
        self.assertEqual(open_time.minute, 30)
        self.assertEqual(open_time.tzinfo.zone, 'America/New_York')
        self.assertTrue(open_time.dst() == datetime.timedelta(hours=1)) # EDT

        self.assertIsNotNone(close_time)
        self.assertEqual(close_time.hour, 16)
        self.assertEqual(close_time.tzinfo.zone, 'America/New_York')
        self.assertTrue(close_time.dst() == datetime.timedelta(hours=1)) # EDT

    def test_get_market_open_close_on_dst_end_day(self):
        # DST ends Nov 5, 2023 (2 AM becomes 1 AM again)
        # Market open/close times are well after the transition.
        dst_end_date = datetime.date(2023, 11, 5)
        open_time, close_time = get_market_open_close_et(dst_end_date)
        self.assertIsNotNone(open_time)
        self.assertEqual(open_time.hour, 9)
        self.assertEqual(open_time.minute, 30)
        self.assertEqual(open_time.tzinfo.zone, 'America/New_York')
        self.assertTrue(open_time.dst() == datetime.timedelta(0)) # EST

        self.assertIsNotNone(close_time)
        self.assertEqual(close_time.hour, 16)
        self.assertEqual(close_time.tzinfo.zone, 'America/New_York')
        self.assertTrue(close_time.dst() == datetime.timedelta(0)) # EST

if __name__ == '__main__':
    unittest.main()
