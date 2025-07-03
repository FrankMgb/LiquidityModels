import unittest
import whenever # Main datetime library
from src.utils.time_utils import convert_to_et, get_market_open_close_et, TARGET_TZ
from datetime import datetime as std_datetime, date as std_date, timezone as std_timezone # For creating some test inputs

class TestTimeUtils(unittest.TestCase):

    def test_convert_to_et_naive_py_datetime_assume_utc(self):
        # Naive Python datetime, to be interpreted as UTC
        naive_py_dt_utc = std_datetime(2023, 10, 26, 14, 30) # 2:30 PM UTC
        et_dt = convert_to_et(naive_py_dt_utc, original_tz_str='UTC')
        self.assertIsNotNone(et_dt)
        self.assertIsInstance(et_dt, whenever.ZonedDateTime)
        self.assertEqual(et_dt.tz, TARGET_TZ)
        # 2023-10-26 14:30 UTC is 2023-10-26 10:30 EDT
        self.assertEqual(et_dt.year, 2023)
        self.assertEqual(et_dt.month, 10)
        self.assertEqual(et_dt.day, 26)
        self.assertEqual(et_dt.hour, 10)
        self.assertEqual(et_dt.minute, 30)
        # Check offset for EDT (-4 hours)
        self.assertEqual(et_dt.offset.in_hours(), -4)


    def test_convert_to_et_naive_py_datetime_assume_london(self):
        # Naive Python datetime, to be interpreted as Europe/London
        # On 2023-08-15, London is in BST (UTC+1)
        naive_py_dt_london = std_datetime(2023, 8, 15, 15, 30) # 3:30 PM London time
        et_dt = convert_to_et(naive_py_dt_london, original_tz_str='Europe/London')
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.tz, TARGET_TZ)
        # 15:30 BST (UTC+1) is 14:30 UTC.
        # 14:30 UTC is 10:30 EDT (UTC-4).
        self.assertEqual(et_dt.hour, 10)
        self.assertEqual(et_dt.minute, 30)
        self.assertEqual(et_dt.offset.in_hours(), -4) # EDT

    def test_convert_to_et_aware_py_datetime_utc(self):
        # Aware Python datetime (UTC)
        aware_py_dt_utc = std_datetime(2023, 11, 5, 14, 30, tzinfo=std_timezone.utc) # 2:30 PM UTC
        et_dt = convert_to_et(aware_py_dt_utc)
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.tz, TARGET_TZ)
        # 2023-11-05 14:30 UTC. NY is EST (UTC-5) on this date after 2 AM EDT.
        # So, 14:30 UTC is 9:30 AM EST.
        self.assertEqual(et_dt.hour, 9)
        self.assertEqual(et_dt.minute, 30)
        self.assertEqual(et_dt.offset.in_hours(), -5) # EST

    def test_convert_to_et_naive_py_datetime_no_original_tz(self):
        # Naive Python datetime, no original_tz_str. Should fail.
        ambiguous_naive_py_dt = std_datetime(2023, 10, 26, 10, 30)
        et_dt = convert_to_et(ambiguous_naive_py_dt, original_tz_str=None)
        self.assertIsNone(et_dt) # Expect None as it's ambiguous

    def test_convert_to_et_whenever_instant(self):
        # whenever.Instant (already UTC)
        instant = whenever.Instant.from_utc(2023, 10, 26, 14, 30) # 2:30 PM UTC
        et_dt = convert_to_et(instant)
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.hour, 10) # 10:30 AM EDT
        self.assertEqual(et_dt.offset.in_hours(), -4)

    def test_convert_to_et_whenever_zdt_already_et(self):
        zdt_et = whenever.ZonedDateTime(2023, 10, 26, 10, 30, tz=TARGET_TZ)
        et_dt = convert_to_et(zdt_et)
        self.assertEqual(et_dt, zdt_et) # Should return the same object or equivalent

    def test_convert_to_et_whenever_zdt_other_zone(self):
        zdt_london = whenever.ZonedDateTime(2023, 8, 15, 15, 30, tz="Europe/London") # 3:30 PM London
        et_dt = convert_to_et(zdt_london)
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.hour, 10) # 10:30 AM EDT
        self.assertEqual(et_dt.offset.in_hours(), -4)

    def test_convert_to_et_whenever_plaindatetime_with_original_tz(self):
        pdt = whenever.PlainDateTime(2023, 8, 15, 15, 30) # Treat as 3:30 PM London
        et_dt = convert_to_et(pdt, original_tz_str="Europe/London")
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.hour, 10) # 10:30 AM EDT
        self.assertEqual(et_dt.offset.in_hours(), -4)

    def test_convert_to_et_whenever_plaindatetime_no_original_tz(self):
        pdt = whenever.PlainDateTime(2023, 8, 15, 15, 30)
        et_dt = convert_to_et(pdt, original_tz_str=None) # Should be None
        self.assertIsNone(et_dt)

    def test_convert_to_et_unix_timestamp(self):
        unix_ts = 1678624200 # March 12, 2023 08:30 AM ET (EDT)
        et_dt = convert_to_et(unix_ts)
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.year, 2023)
        self.assertEqual(et_dt.month, 3)
        self.assertEqual(et_dt.day, 12)
        self.assertEqual(et_dt.hour, 8)
        self.assertEqual(et_dt.minute, 30)
        self.assertEqual(et_dt.offset.in_hours(), -4) # EDT

    def test_convert_to_et_string_iso_utc(self):
        iso_str_utc = "2023-08-15T13:30:00Z"
        et_dt = convert_to_et(iso_str_utc) # No original_tz_str needed for UTC string
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.hour, 9) # 9:30 AM EDT
        self.assertEqual(et_dt.offset.in_hours(), -4)

    def test_convert_to_et_string_iso_offset(self):
        iso_str_offset = "2023-08-15T15:30:00+02:00" # CEST
        et_dt = convert_to_et(iso_str_offset)
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.hour, 9) # 9:30 AM EDT
        self.assertEqual(et_dt.offset.in_hours(), -4)

    def test_convert_to_et_string_naive_assume_et(self):
        # convert_to_et, when parsing a naive string via pandas, and original_tz_str is not passed from caller,
        # will internally assume TARGET_TZ for the naive datetime string.
        naive_str = "2023-10-26 10:30:00"
        et_dt = convert_to_et(naive_str) # original_tz_str=None, convert_to_et assumes TARGET_TZ
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.hour, 10)
        self.assertEqual(et_dt.minute, 30)
        self.assertEqual(et_dt.offset.in_hours(), -4) # EDT

    def test_convert_to_et_string_naive_assume_other_tz(self):
        naive_str = "2023-08-15 15:30:00" # As London time
        et_dt = convert_to_et(naive_str, original_tz_str="Europe/London")
        self.assertIsNotNone(et_dt)
        self.assertEqual(et_dt.hour, 10) # 10:30 AM EDT
        self.assertEqual(et_dt.offset.in_hours(), -4)

    def test_convert_to_et_dst_spring_forward_non_existent(self):
        # 2024-03-10 02:30:00 does not exist in America/New_York
        # convert_to_et should return None due to disambiguate='raise'
        # when assuming TARGET_TZ for this naive string.
        non_existent_str = "2024-03-10 02:30:00"
        et_dt = convert_to_et(non_existent_str, original_tz_str=TARGET_TZ)
        self.assertIsNone(et_dt) # Expecting None because SkippedTime should be caught

    def test_convert_to_et_dst_fall_back_ambiguous(self):
        # 2023-11-05 01:30:00 is ambiguous in America/New_York
        # convert_to_et should return None due to disambiguate='raise'
        ambiguous_str = "2023-11-05 01:30:00"
        et_dt = convert_to_et(ambiguous_str, original_tz_str=TARGET_TZ)
        self.assertIsNone(et_dt) # Expecting None because RepeatedTime should be caught

    # --- Tests for get_market_open_close_et ---
    def test_get_market_open_close_et_summer_edt(self):
        w_date = whenever.Date(2023, 8, 15) # EDT
        open_dt, close_dt = get_market_open_close_et(w_date)
        self.assertIsNotNone(open_dt)
        self.assertIsNotNone(close_dt)
        self.assertEqual(open_dt.hour, 9)
        self.assertEqual(open_dt.minute, 30)
        self.assertEqual(open_dt.offset.in_hours(), -4) # EDT
        self.assertEqual(close_dt.hour, 16)
        self.assertEqual(close_dt.offset.in_hours(), -4) # EDT
        self.assertEqual(open_dt.tz, TARGET_TZ)

    def test_get_market_open_close_et_winter_est(self):
        w_date = whenever.Date(2023, 11, 6) # EST
        open_dt, close_dt = get_market_open_close_et(w_date)
        self.assertIsNotNone(open_dt)
        self.assertIsNotNone(close_dt)
        self.assertEqual(open_dt.hour, 9)
        self.assertEqual(open_dt.minute, 30)
        self.assertEqual(open_dt.offset.in_hours(), -5) # EST
        self.assertEqual(close_dt.hour, 16)
        self.assertEqual(close_dt.offset.in_hours(), -5) # EST

    def test_get_market_open_close_et_custom_times(self):
        w_date = whenever.Date(2023, 10, 10)
        open_dt, close_dt = get_market_open_close_et(w_date, open_time_str="08:00", close_time_str="14:30")
        self.assertIsNotNone(open_dt)
        self.assertEqual(open_dt.hour, 8)
        self.assertIsNotNone(close_dt)
        self.assertEqual(close_dt.hour, 14)
        self.assertEqual(close_dt.minute, 30)

    def test_get_market_open_close_et_invalid_time_str(self):
        w_date = whenever.Date(2023, 1, 1)
        open_dt, close_dt = get_market_open_close_et(w_date, open_time_str="99:00")
        self.assertIsNone(open_dt)
        self.assertIsNone(close_dt)

    def test_get_market_open_close_et_py_date_input(self):
        py_date = std_date(2023, 7, 1) # Python date
        open_dt, close_dt = get_market_open_close_et(py_date)
        self.assertIsNotNone(open_dt)
        self.assertEqual(open_dt.year, 2023)
        self.assertEqual(open_dt.month, 7)
        self.assertEqual(open_dt.day, 1)
        self.assertEqual(open_dt.hour, 9)

    def test_get_market_open_close_dst_spring_forward_market_hours_ok(self):
        # March 10, 2024: 2 AM -> 3 AM. Market hours 9:30-16:00 are fine.
        date_dst_start = whenever.Date(2024, 3, 10)
        op, cl = get_market_open_close_et(date_dst_start)
        self.assertIsNotNone(op)
        self.assertEqual(op.hour, 9)
        self.assertEqual(op.offset.in_hours(), -4) # EDT
        self.assertIsNotNone(cl)

    def test_get_market_open_close_dst_fall_back_market_hours_ok(self):
        # Nov 5, 2023: 1:XX AM happens twice. Market hours 9:30-16:00 are fine (EST).
        date_dst_end = whenever.Date(2023, 11, 5)
        op, cl = get_market_open_close_et(date_dst_end)
        self.assertIsNotNone(op)
        self.assertEqual(op.hour, 9)
        self.assertEqual(op.offset.in_hours(), -5) # EST
        self.assertIsNotNone(cl)

if __name__ == '__main__':
    unittest.main()
