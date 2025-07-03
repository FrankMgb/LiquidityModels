import unittest
import whenever # Main datetime library
from src.data_handler.market_data_loader import (
    process_data_timestamps,
    calculate_initial_balance,
    is_within_initial_balance,
    load_raw_data
)
from src.utils.time_utils import TARGET_TZ # For checks and creating test data
from datetime import datetime as std_datetime # For some raw input types

class TestMarketDataLoader(unittest.TestCase):

    def test_process_data_timestamps_varied_inputs(self):
        raw_data_samples = load_raw_data() # Use a few samples from the actual loader

        # We need to be careful with default_original_tz here.
        # If a naive string like "2023-10-25 09:30:00" is passed, and default_original_tz is 'America/New_York',
        # convert_to_et will treat it as ET.
        processed = process_data_timestamps(raw_data_samples, default_original_tz='America/New_York')

        # Check a few key conversions based on load_raw_data samples
        # 1. "2023-10-25 09:30:00" (naive string, assumed ET)
        self.assertIsNotNone(processed[0]['timestamp_et'])
        self.assertEqual(processed[0]['timestamp_et'].hour, 9)
        self.assertEqual(processed[0]['timestamp_et'].minute, 30)
        self.assertEqual(processed[0]['timestamp_et'].offset.in_hours(), -4) # EDT

        # 2. "2023-10-25 10:00:00 Europe/London" (string with TZ)
        #    10:00 London (BST = UTC+1) is 09:00 UTC. 09:00 UTC is 05:00 EDT.
        self.assertIsNotNone(processed[1]['timestamp_et'])
        self.assertEqual(processed[1]['timestamp_et'].hour, 5)
        self.assertEqual(processed[1]['timestamp_et'].offset.in_hours(), -4) # EDT

        # 3. Unix timestamp 1678624200 (March 12, 2023 08:30 AM EDT)
        self.assertIsNotNone(processed[5]['timestamp_et']) # Index 5 in load_raw_data
        self.assertEqual(processed[5]['timestamp_et'].hour, 8)
        self.assertEqual(processed[5]['timestamp_et'].minute, 30)
        self.assertEqual(processed[5]['timestamp_et'].offset.in_hours(), -4) # EDT

        # 4. "2024-03-10 02:30:00" (non-existent in ET, if assumed ET)
        #    convert_to_et with original_tz_str='America/New_York' (due to default_original_tz)
        #    and disambiguate='raise' should result in None.
        self.assertIsNone(processed[7]['timestamp_et']) # Index 7 in load_raw_data

    def test_process_data_timestamps_assume_utc_for_naive_inputs(self):
        raw_data = [
            {"timestamp": "2023-10-25 09:30:00", "value": 1}, # Naive string
            {"timestamp": std_datetime(2023, 10, 25, 14, 30, 0), "value": 2}, # Naive Python datetime
        ]
        # Here, we explicitly say naive inputs should be treated as UTC
        processed = process_data_timestamps(raw_data, default_original_tz='UTC')

        # 1. "2023-10-25 09:30:00" (as UTC) -> 05:30 EDT
        self.assertIsNotNone(processed[0]['timestamp_et'])
        self.assertEqual(processed[0]['timestamp_et'].hour, 5)
        self.assertEqual(processed[0]['timestamp_et'].minute, 30)
        self.assertEqual(processed[0]['timestamp_et'].offset.in_hours(), -4) # EDT

        # 2. Python datetime(2023, 10, 25, 14, 30, 0) (as UTC) -> 10:30 EDT
        self.assertIsNotNone(processed[1]['timestamp_et'])
        self.assertEqual(processed[1]['timestamp_et'].hour, 10)
        self.assertEqual(processed[1]['timestamp_et'].minute, 30)
        self.assertEqual(processed[1]['timestamp_et'].offset.in_hours(), -4) # EDT

    def test_calculate_initial_balance_standard_day_edt(self):
        # Timestamps are whenever.ZonedDateTime in ET
        data = [
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 9, 29, 0, tz=TARGET_TZ), 'high': 100, 'low': 99},
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 9, 30, 0, tz=TARGET_TZ), 'high': 101, 'low': 100},
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 9, 45, 0, tz=TARGET_TZ), 'high': 103, 'low': 100.5},
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 10, 29, 0, tz=TARGET_TZ), 'high': 102, 'low': 101.5},
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 10, 30, 0, tz=TARGET_TZ), 'high': 104, 'low': 103},
        ]
        trade_date = whenever.Date(2023, 8, 15)
        ib_info = calculate_initial_balance(data)

        self.assertIn(trade_date, ib_info)
        self.assertEqual(ib_info[trade_date]['ib_high'], 103)
        self.assertEqual(ib_info[trade_date]['ib_low'], 100)
        expected_ib_start = whenever.ZonedDateTime(2023, 8, 15, 9, 30, tz=TARGET_TZ)
        expected_ib_end = whenever.ZonedDateTime(2023, 8, 15, 10, 30, tz=TARGET_TZ)
        self.assertEqual(ib_info[trade_date]['ib_start_et'], expected_ib_start)
        self.assertEqual(ib_info[trade_date]['ib_end_et'], expected_ib_end)
        self.assertEqual(ib_info[trade_date]['ib_start_et'].offset.in_hours(), -4) # Check EDT

    def test_calculate_initial_balance_standard_day_est(self):
        # Day in EST
        data = [
            {'timestamp_et': whenever.ZonedDateTime(2023, 11, 6, 9, 29, 0, tz=TARGET_TZ), 'high': 200, 'low': 199},
            {'timestamp_et': whenever.ZonedDateTime(2023, 11, 6, 9, 30, 0, tz=TARGET_TZ), 'high': 201, 'low': 200},
            {'timestamp_et': whenever.ZonedDateTime(2023, 11, 6, 10, 0, 0, tz=TARGET_TZ), 'high': 202, 'low': 200.5},
            {'timestamp_et': whenever.ZonedDateTime(2023, 11, 6, 10, 30, 0, tz=TARGET_TZ), 'high': 204, 'low': 203},
        ]
        trade_date = whenever.Date(2023, 11, 6)
        ib_info = calculate_initial_balance(data)
        self.assertIn(trade_date, ib_info)
        self.assertEqual(ib_info[trade_date]['ib_high'], 202) # High is 201, 202
        self.assertEqual(ib_info[trade_date]['ib_low'], 200)  # Low is 200, 200.5
        self.assertEqual(ib_info[trade_date]['ib_start_et'].offset.in_hours(), -5) # Check EST

    def test_calculate_initial_balance_no_data_in_period(self):
        data = [
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 9, 0, 0, tz=TARGET_TZ), 'high': 100, 'low': 99},
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 11, 0, 0, tz=TARGET_TZ), 'high': 102, 'low': 101},
        ]
        trade_date = whenever.Date(2023, 8, 15)
        ib_info = calculate_initial_balance(data)
        self.assertIn(trade_date, ib_info)
        self.assertIsNone(ib_info[trade_date]['ib_high'])
        self.assertIsNone(ib_info[trade_date]['ib_low'])
        self.assertIn("message", ib_info[trade_date])

    def test_calculate_initial_balance_weekend_skip(self):
        saturday_date = whenever.Date(2023, 10, 28) # A Saturday
        self.assertEqual(saturday_date.day_of_week(), whenever.Weekday.SATURDAY)
        data = [
            {'timestamp_et': whenever.ZonedDateTime(2023, 10, 28, 9, 30, 0, tz=TARGET_TZ), 'high': 100, 'low': 99},
        ]
        ib_info = calculate_initial_balance(data)
        self.assertIn(saturday_date, ib_info)
        self.assertIn("error", ib_info[saturday_date])
        self.assertEqual(ib_info[saturday_date]['error'], "Weekend, IB not calculated.")

    def test_calculate_initial_balance_custom_ib_times(self):
        data = [
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 9, 59, 0, tz=TARGET_TZ), 'high': 100, 'low': 99},
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 10, 0, 0, tz=TARGET_TZ), 'high': 101, 'low': 100.5},
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 10, 59, 0, tz=TARGET_TZ), 'high': 103, 'low': 101.5},
            {'timestamp_et': whenever.ZonedDateTime(2023, 8, 15, 11, 0, 0, tz=TARGET_TZ), 'high': 104, 'low': 103.5},
        ]
        trade_date = whenever.Date(2023, 8, 15)
        ib_info = calculate_initial_balance(data, ib_start_time_str="10:00", ib_end_time_str="11:00")
        self.assertIn(trade_date, ib_info)
        self.assertEqual(ib_info[trade_date]['ib_high'], 103)
        self.assertEqual(ib_info[trade_date]['ib_low'], 100.5)
        expected_ib_start = whenever.ZonedDateTime(2023, 8, 15, 10, 0, 0, tz=TARGET_TZ)
        expected_ib_end = whenever.ZonedDateTime(2023, 8, 15, 11, 0, 0, tz=TARGET_TZ)
        self.assertEqual(ib_info[trade_date]['ib_start_et'], expected_ib_start)
        self.assertEqual(ib_info[trade_date]['ib_end_et'], expected_ib_end)

    def test_is_within_initial_balance(self):
        ib_start = whenever.ZonedDateTime(2023, 8, 15, 9, 30, 0, tz=TARGET_TZ)
        ib_end = whenever.ZonedDateTime(2023, 8, 15, 10, 30, 0, tz=TARGET_TZ)

        time_before = ib_start.subtract(seconds=1)
        time_at_start = ib_start
        time_inside = ib_start.add(minutes=15)
        time_at_end_exclusive = ib_end.subtract(seconds=1)
        time_at_end_inclusive = ib_end # This should be false as IB is [start, end)

        self.assertFalse(is_within_initial_balance(time_before, ib_start, ib_end))
        self.assertTrue(is_within_initial_balance(time_at_start, ib_start, ib_end))
        self.assertTrue(is_within_initial_balance(time_inside, ib_start, ib_end))
        self.assertTrue(is_within_initial_balance(time_at_end_exclusive, ib_start, ib_end))
        self.assertFalse(is_within_initial_balance(time_at_end_inclusive, ib_start, ib_end))

    def test_is_within_initial_balance_wrong_type(self):
        # Test with a non-whenever type for one of the arguments
        ib_start = whenever.ZonedDateTime(2023, 8, 15, 9, 30, 0, tz=TARGET_TZ)
        ib_end = whenever.ZonedDateTime(2023, 8, 15, 10, 30, 0, tz=TARGET_TZ)
        py_dt = std_datetime(2023, 8, 15, 10, 0, 0) # Python datetime
        self.assertFalse(is_within_initial_balance(py_dt, ib_start, ib_end))


if __name__ == '__main__':
    unittest.main()
