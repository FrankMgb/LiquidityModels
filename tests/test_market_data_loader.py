import unittest
import datetime
import pytz
from src.data_handler.market_data_loader import (
    process_data_timestamps,
    calculate_initial_balance,
    is_within_initial_balance,
    load_raw_data # To get some varied inputs
)
from src.utils.time_utils import convert_to_et # For creating test data

class TestMarketDataLoader(unittest.TestCase):

    def setUp(self):
        self.et_tz = pytz.timezone('America/New_York')
        self.utc_tz = pytz.utc

    def test_process_data_timestamps_varied_inputs(self):
        raw_data = [
            {"timestamp": "2023-10-25 09:30:00", "value": 1}, # Naive, assume ET
            {"timestamp": "2023-10-25 10:00:00 Europe/London", "value": 2}, # Explicit TZ
            {"timestamp": datetime.datetime(2023, 10, 25, 14, 30, 0), "value": 3}, # Naive datetime, assume ET
            {"timestamp": self.utc_tz.localize(datetime.datetime(2023, 11, 5, 5, 30, 0)), "value": 4}, # Aware UTC (1:30 AM EDT)
            {"timestamp": 1678624200, "value": 5}, # Unix timestamp (Mar 12, 2023 9:30 AM EDT)
            {"timestamp": "2023-08-15T13:30:00Z", "value": 6} # ISO format UTC
        ]

        processed = process_data_timestamps(raw_data, default_original_tz='America/New_York')

        # Expected ET times:
        # 1. 2023-10-25 09:30:00 ET (EDT)
        # 2. 2023-10-25 05:00:00 ET (EDT) from London 10:00 BST
        # 3. 2023-10-25 14:30:00 ET (EDT)
        # 4. 2023-11-05 01:30:00 ET (EDT) - first occurrence
        # 5. 2023-03-12 08:30:00 ET (EDT) - Unix timestamp 1678624200 is 08:30 EDT
        # 6. 2023-08-15 09:30:00 ET (EDT) from 13:30 UTC

        self.assertEqual(processed[0]['timestamp_et'], self.et_tz.localize(datetime.datetime(2023, 10, 25, 9, 30, 0)))
        self.assertEqual(processed[1]['timestamp_et'], self.et_tz.normalize(pytz.timezone('Europe/London').localize(datetime.datetime(2023,10,25,10,0,0)).astimezone(self.et_tz)))
        self.assertEqual(processed[2]['timestamp_et'], self.et_tz.localize(datetime.datetime(2023, 10, 25, 14, 30, 0)))
        # For the UTC time that falls into the DST overlap:
        # 2023-11-05 05:30:00 UTC is 2023-11-05 01:30:00 EDT (UTC-4) as DST hasn't ended *yet* at this exact UTC instant.
        # The switch happens at 2 AM EDT -> 1 AM EST.
        self.assertEqual(processed[3]['timestamp_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z'), "2023-11-05 01:30:00 EDT-0400")
        self.assertEqual(processed[4]['timestamp_et'], self.et_tz.localize(datetime.datetime(2023, 3, 12, 8, 30, 0))) # Corrected expectation
        self.assertEqual(processed[5]['timestamp_et'], self.et_tz.normalize(self.utc_tz.localize(datetime.datetime(2023,8,15,13,30,0)).astimezone(self.et_tz)))

    def test_process_data_timestamps_assume_utc_for_naive(self):
        raw_data = [
            {"timestamp": "2023-10-25 09:30:00", "value": 1}, # Naive, assume UTC this time
            {"timestamp": datetime.datetime(2023, 10, 25, 14, 30, 0), "value": 3}, # Naive datetime, assume UTC
        ]
        processed = process_data_timestamps(raw_data, default_original_tz='UTC')
        # 1. 2023-10-25 09:30:00 UTC -> 2023-10-25 05:30:00 EDT
        # 2. 2023-10-25 14:30:00 UTC -> 2023-10-25 10:30:00 EDT
        self.assertEqual(processed[0]['timestamp_et'], self.et_tz.normalize(self.utc_tz.localize(datetime.datetime(2023,10,25,9,30,0)).astimezone(self.et_tz)))
        self.assertEqual(processed[1]['timestamp_et'], self.et_tz.normalize(self.utc_tz.localize(datetime.datetime(2023,10,25,14,30,0)).astimezone(self.et_tz)))


    def test_calculate_initial_balance_standard_day(self):
        # Test data for a single day, within EDT period
        # Timestamps should already be ET and aware
        data = [
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 29, 0)), 'high': 100, 'low': 99}, # Before IB
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 30, 0)), 'high': 101, 'low': 100}, # IB Start
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 45, 0)), 'high': 103, 'low': 100.5},# In IB
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 29, 0)), 'high': 102, 'low': 101.5},# In IB (ends before 10:30)
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 30, 0)), 'high': 104, 'low': 103}, # After IB
        ]
        trade_date = datetime.date(2023, 8, 15)
        ib_info = calculate_initial_balance(data)

        self.assertIn(trade_date, ib_info)
        self.assertEqual(ib_info[trade_date]['ib_high'], 103)
        self.assertEqual(ib_info[trade_date]['ib_low'], 100)
        self.assertEqual(ib_info[trade_date]['ib_start_et'], self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 30)))
        self.assertEqual(ib_info[trade_date]['ib_end_et'], self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 30)))

    def test_calculate_initial_balance_multi_day(self):
        data = [
            # Day 1 (EDT)
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 30, 0)), 'high': 101, 'low': 100},
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 0, 0)), 'high': 102, 'low': 100.5},
            # Day 2 (EST) - after DST change
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 11, 6, 9, 30, 0)), 'high': 201, 'low': 200}, # EST
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 11, 6, 10, 0, 0)), 'high': 202, 'low': 200.5},# EST
        ]
        ib_info = calculate_initial_balance(data)

        date1 = datetime.date(2023, 8, 15)
        date2 = datetime.date(2023, 11, 6)

        self.assertIn(date1, ib_info)
        self.assertEqual(ib_info[date1]['ib_high'], 102)
        self.assertEqual(ib_info[date1]['ib_low'], 100)

        self.assertIn(date2, ib_info)
        self.assertEqual(ib_info[date2]['ib_high'], 202)
        self.assertEqual(ib_info[date2]['ib_low'], 200)
        self.assertTrue(ib_info[date1]['ib_start_et'].dst() == datetime.timedelta(hours=1)) # EDT
        self.assertTrue(ib_info[date2]['ib_start_et'].dst() == datetime.timedelta(0))    # EST

    def test_calculate_initial_balance_no_data_in_period(self):
        data = [
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 0, 0)), 'high': 100, 'low': 99},  # Before
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 11, 0, 0)), 'high': 102, 'low': 101}, # After
        ]
        trade_date = datetime.date(2023, 8, 15)
        ib_info = calculate_initial_balance(data)
        self.assertIn(trade_date, ib_info)
        self.assertIsNone(ib_info[trade_date]['ib_high'])
        self.assertIsNone(ib_info[trade_date]['ib_low'])
        self.assertIn("message", ib_info[trade_date])
        self.assertEqual(ib_info[trade_date]['message'], "No data within IB period.")

    def test_calculate_initial_balance_weekend_skip(self):
        saturday = datetime.date(2023, 10, 28) # A Saturday
        data = [
            {'timestamp_et': self.et_tz.localize(datetime.datetime(saturday.year, saturday.month, saturday.day, 9, 30, 0)), 'high': 100, 'low': 99},
        ]
        ib_info = calculate_initial_balance(data)
        self.assertIn(saturday, ib_info)
        self.assertIn("error", ib_info[saturday])
        self.assertEqual(ib_info[saturday]['error'], "Weekend, IB not calculated.")

    def test_calculate_initial_balance_custom_ib_times(self):
        data = [
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 59, 0)), 'high': 100, 'low': 99},
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 0, 0)), 'high': 101, 'low': 100.5}, # Start
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 30, 0)), 'high': 103, 'low': 102},   # In
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 59, 0)), 'high': 102.5, 'low':101.5},# In (end before 11:00)
            {'timestamp_et': self.et_tz.localize(datetime.datetime(2023, 8, 15, 11, 0, 0)), 'high': 104, 'low': 103.5}, # After
        ]
        trade_date = datetime.date(2023, 8, 15)
        ib_info = calculate_initial_balance(data, ib_start_time_str="10:00", ib_end_time_str="11:00")
        self.assertIn(trade_date, ib_info)
        self.assertEqual(ib_info[trade_date]['ib_high'], 103)
        self.assertEqual(ib_info[trade_date]['ib_low'], 100.5)
        self.assertEqual(ib_info[trade_date]['ib_start_et'], self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 0, 0)))
        self.assertEqual(ib_info[trade_date]['ib_end_et'], self.et_tz.localize(datetime.datetime(2023, 8, 15, 11, 0, 0)))

    def test_is_within_initial_balance(self):
        ib_start_et = self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 30))
        ib_end_et = self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 30))

        time_before = self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 29, 59))
        time_at_start = self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 30, 0))
        time_inside = self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 0, 0))
        time_at_end_exclusive = self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 29, 59))
        time_at_end_inclusive = self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 30, 0)) # This should be false
        time_after = self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 30, 1))

        self.assertFalse(is_within_initial_balance(time_before, ib_start_et, ib_end_et))
        self.assertTrue(is_within_initial_balance(time_at_start, ib_start_et, ib_end_et))
        self.assertTrue(is_within_initial_balance(time_inside, ib_start_et, ib_end_et))
        self.assertTrue(is_within_initial_balance(time_at_end_exclusive, ib_start_et, ib_end_et))
        self.assertFalse(is_within_initial_balance(time_at_end_inclusive, ib_start_et, ib_end_et))
        self.assertFalse(is_within_initial_balance(time_after, ib_start_et, ib_end_et))

    def test_is_within_initial_balance_naive_inputs(self):
        # Function expects aware times, should warn and return False or raise error
        # Currently it prints a warning and returns False.
        ib_start_et = self.et_tz.localize(datetime.datetime(2023, 8, 15, 9, 30))
        ib_end_et = self.et_tz.localize(datetime.datetime(2023, 8, 15, 10, 30))
        naive_time = datetime.datetime(2023, 8, 15, 10, 0, 0)

        self.assertFalse(is_within_initial_balance(naive_time, ib_start_et, ib_end_et))
        self.assertFalse(is_within_initial_balance(ib_start_et, naive_time, ib_end_et)) # if ib_start is naive
        self.assertFalse(is_within_initial_balance(ib_start_et, ib_start_et, naive_time))# if ib_end is naive

if __name__ == '__main__':
    unittest.main()
