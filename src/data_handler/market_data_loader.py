import pandas as pd # Still useful for creating DataFrames from raw data if needed later
import whenever # Main library for datetime operations
from src.utils.time_utils import convert_to_et, get_market_open_close_et
# Removed: import datetime, import pytz from standard library

def load_raw_data():
    """
    Simulates loading raw market data.
    Returns a list of dictionaries, where each dictionary represents a data point (e.g., a candle).
    Timestamps are intentionally varied to test conversion logic.
    """
    sample_data = [
        {
            "timestamp": "2023-10-25 09:30:00", # Naive, will be assumed ET by convert_to_et default for strings
            "open": 150.00, "high": 150.50, "low": 149.80, "close": 150.20, "volume": 1000
        },
        {
            "timestamp": "2023-10-25 10:00:00 Europe/London", # String with timezone (pandas parses this)
            "open": 150.20, "high": 151.00, "low": 150.10, "close": 150.90, "volume": 1200
        },
        {
            # Using python's datetime here to simulate data that might come from other stdlib sources
            "timestamp": pd.Timestamp("2023-10-25 14:30:00").to_pydatetime(), # Naive datetime object, assume ET
            "open": 150.90, "high": 151.20, "low": 150.80, "close": 151.10, "volume": 900
        },
        { # Data for a day with DST change in US (Fall back) - Ambiguous in ET if naive
            # This UTC time is 2023-11-05 01:30:00 EDT (UTC-4)
            "timestamp": pd.Timestamp("2023-11-05 05:30:00Z").to_pydatetime(), # Aware UTC
            "open": 152.00, "high": 152.50, "low": 151.80, "close": 152.20, "volume": 1100
        },
        { # This UTC time is 2023-11-05 01:30:00 EST (UTC-5), the second occurrence
            "timestamp": pd.Timestamp("2023-11-05 06:30:00Z").to_pydatetime(), # Aware UTC
            "open": 152.10, "high": 152.60, "low": 151.90, "close": 152.30, "volume": 1300
        },
        { # Unix timestamp (seconds since epoch)
            "timestamp": 1678624200, # This is March 12, 2023 08:30 AM ET (EDT)
            "open": 155.00, "high": 155.50, "low": 154.80, "close": 155.20, "volume": 1000
        },
         { # ISO format with Z (Zulu/UTC)
            "timestamp": "2023-08-15T13:30:00Z",
            "open": 160.00, "high": 160.50, "low": 159.80, "close": 160.20, "volume": 1000
        },
        { # Non-existent time if assumed ET
            "timestamp": "2024-03-10 02:30:00",
            "open": 161.00, "high": 161.50, "low": 160.80, "close": 161.20, "volume": 1000
        }
    ]
    return sample_data

# The parse_timestamp helper is now effectively integrated into time_utils.convert_to_et
# process_data_timestamps will directly use convert_to_et

def process_data_timestamps(raw_data: list, default_original_tz: str | None = 'America/New_York') -> list:
    """
    Processes raw data to standardize timestamps to Eastern Time (ET) using whenever.ZonedDateTime.

    Args:
        raw_data (list): A list of dictionaries, where each dictionary has a 'timestamp' key.
        default_original_tz (str | None): The timezone to assume for naive timestamp inputs
                                     (Python datetimes or strings parsed as naive by pandas).
                                     If None, naive inputs without explicit TZ might fail conversion.
                                     `convert_to_et` has its own logic for assuming ET for naive strings
                                     if this is not set, but being explicit can be clearer.

    Returns:
        list: Data with 'timestamp_et' values as whenever.ZonedDateTime objects (ET).
              Entries that fail parsing/conversion will have their timestamp_et set to None.
    """
    processed_data = []
    for record in raw_data:
        new_record = record.copy()
        original_ts = new_record.get("timestamp")

        # Pass default_original_tz to convert_to_et.
        # convert_to_et handles various types including strings, Python datetimes, and Unix timestamps.
        # For naive strings, convert_to_et's internal pandas parsing will make them naive py_datetime,
        # then original_tz_str (which is default_original_tz here) will be used.
        # If default_original_tz is None, convert_to_et has a fallback for naive strings to assume TARGET_TZ.
        new_record['timestamp_et'] = convert_to_et(original_ts, original_tz_str=default_original_tz)

        if new_record['timestamp_et'] is None:
            print(f"Record failed timestamp conversion: Original timestamp {original_ts}")

        processed_data.append(new_record)

    return processed_data


def calculate_initial_balance(
    processed_data_et: list,
    ib_start_time_str: str = "09:30",
    ib_end_time_str: str = "10:30"
    # market_tz_str is no longer needed as processed_data_et is already in target ET ZonedDateTime
) -> dict:
    """
    Calculates the Initial Balance (IB) period's start, end, high, and low for each day.
    Assumes processed_data_et contains records with 'timestamp_et' as whenever.ZonedDateTime in ET.

    Args:
        processed_data_et (list): List of data records.
        ib_start_time_str (str): IB start time in "HH:MM" format. Defaults to "09:30".
        ib_end_time_str (str): IB end time in "HH:MM" format. Defaults to "10:30".

    Returns:
        dict: A dictionary where keys are whenever.Date objects and values are
              dictionaries containing:
              {'ib_start_et', 'ib_end_et', 'ib_high', 'ib_low', 'error' (optional)}
    """
    if not processed_data_et:
        return {}

    daily_ib_data = {}

    # Group data by date (using whenever.Date from ZonedDateTime)
    data_by_date = {}
    for record in processed_data_et:
        ts_et = record.get('timestamp_et')
        if ts_et and isinstance(ts_et, whenever.ZonedDateTime):
            record_date = ts_et.date() # This is a whenever.Date
            if record_date not in data_by_date:
                data_by_date[record_date] = []
            data_by_date[record_date].append(record)

    for trade_date, records_for_day in data_by_date.items(): # trade_date is a whenever.Date
        # Skip weekends (Saturday is 6, Sunday is 7 in whenever.Weekday.value)
        # ISO weekday: Monday is 1, Sunday is 7.
        # whenever.Weekday: MONDAY=1 ... SUNDAY=7
        if trade_date.day_of_week().value >= whenever.Weekday.SATURDAY.value: # Saturday or Sunday
            daily_ib_data[trade_date] = {"error": "Weekend, IB not calculated."}
            continue

        # Get IB period start/end for the trade_date using the utility function
        # This ensures DST is handled correctly for constructing these ZonedDateTimes
        ib_start_dt_et, ib_end_dt_et = get_market_open_close_et(
            trade_date,
            open_time_str=ib_start_time_str,
            close_time_str=ib_end_time_str # Using close_time_str for ib_end_time
        )

        if not ib_start_dt_et or not ib_end_dt_et:
            daily_ib_data[trade_date] = {"error": f"Could not determine IB period for {trade_date.format_common_iso()} using times {ib_start_time_str}-{ib_end_time_str}."}
            continue

        ib_period_records = []
        for record in records_for_day:
            ts_et = record['timestamp_et'] # This is a whenever.ZonedDateTime
            # whenever ZonedDateTime comparison is exact and DST-aware
            if ts_et and ib_start_dt_et <= ts_et < ib_end_dt_et:
                ib_period_records.append(record)

        if not ib_period_records:
            daily_ib_data[trade_date] = {
                "ib_start_et": ib_start_dt_et,
                "ib_end_et": ib_end_dt_et,
                "ib_high": None,
                "ib_low": None,
                "message": "No data within IB period."
            }
            continue

        ib_high = max(r['high'] for r in ib_period_records if 'high' in r and r['high'] is not None)
        ib_low = min(r['low'] for r in ib_period_records if 'low' in r and r['low'] is not None)

        daily_ib_data[trade_date] = {
            "ib_start_et": ib_start_dt_et,
            "ib_end_et": ib_end_dt_et,
            "ib_high": ib_high,
            "ib_low": ib_low
        }

    return daily_ib_data

def is_within_initial_balance(
    timestamp_et: whenever.ZonedDateTime,
    ib_start_et: whenever.ZonedDateTime,
    ib_end_et: whenever.ZonedDateTime
) -> bool:
    """
    Checks if a given whenever.ZonedDateTime falls within the Initial Balance period.

    Args:
        timestamp_et: The ZonedDateTime to check (must be in ET).
        ib_start_et: The ZonedDateTime start of the IB period (ET).
        ib_end_et: The ZonedDateTime end of the IB period (ET).

    Returns:
        bool: True if the timestamp is within the IB period, False otherwise.
    """
    if not all(isinstance(t, whenever.ZonedDateTime) for t in [timestamp_et, ib_start_et, ib_end_et]):
        print("Warning: is_within_initial_balance expects all arguments to be whenever.ZonedDateTime objects.")
        return False
    # Ensure all are in the same timezone for robust comparison, though they should be ET.
    # This is mostly a sanity check if inputs could come from varied sources.
    # However, our design implies they are already correct ET ZonedDateTimes.
    # TARGET_TZ = "America/New_York" # Defined in time_utils
    # if not (timestamp_et.tz == TARGET_TZ and ib_start_et.tz == TARGET_TZ and ib_end_et.tz == TARGET_TZ):
    #    print(f"Warning: Not all timestamps are in {TARGET_TZ} for is_within_initial_balance.")
    #    return False

    return ib_start_et <= timestamp_et < ib_end_et


if __name__ == '__main__':
    print("--- Loading Raw Data (whenever version) ---")
    raw_market_data = load_raw_data()

    print("\n--- Processing Data Timestamps (default_original_tz='America/New_York') ---")
    processed_market_data = process_data_timestamps(raw_market_data)
    for i, item in enumerate(processed_market_data):
        print(f"Record {i+1}: Original: '{item['timestamp']}'")
        if item['timestamp_et']:
            print(f"  -> ET: {item['timestamp_et'].format_common_iso()} ({item['timestamp_et'].tz})")
        else:
            print(f"  -> Failed to convert")

    print("\n--- Calculating Initial Balance (9:30 AM - 10:30 AM ET) ---")
    valid_processed_data = [r for r in processed_market_data if r['timestamp_et'] is not None]

    initial_balance_info = calculate_initial_balance(valid_processed_data)
    # Sort by date for consistent output
    sorted_ib_dates = sorted(initial_balance_info.keys())

    for date_key in sorted_ib_dates:
        ib_data = initial_balance_info[date_key]
        print(f"\nDate: {date_key.format_common_iso()}")
        if "error" in ib_data:
            print(f"  Error: {ib_data['error']}")
        elif "message" in ib_data:
            print(f"  IB Start: {ib_data['ib_start_et'].format_common_iso() if ib_data.get('ib_start_et') else 'N/A'}")
            print(f"  IB End:   {ib_data['ib_end_et'].format_common_iso() if ib_data.get('ib_end_et') else 'N/A'}")
            print(f"  Message: {ib_data['message']}")
        else:
            print(f"  IB Start: {ib_data['ib_start_et'].format_common_iso()}")
            print(f"  IB End:   {ib_data['ib_end_et'].format_common_iso()}")
            print(f"  IB High:  {ib_data['ib_high']}")
            print(f"  IB Low:   {ib_data['ib_low']}")

            # Example usage of is_within_initial_balance
            # Pick a timestamp from the original valid_processed_data that falls on this date_key
            sample_record_for_day = next((r for r in valid_processed_data if r['timestamp_et'].date() == date_key), None)
            if sample_record_for_day:
                ts_to_check = sample_record_for_day['timestamp_et']
                is_in_ib = is_within_initial_balance(ts_to_check,
                                                     ib_data['ib_start_et'],
                                                     ib_data['ib_end_et'])
                print(f"  Timestamp {ts_to_check.format_common_iso()} within its IB? {is_in_ib}")


    print("\n--- Calculating Initial Balance (Custom 08:00 AM - 09:00 AM ET) ---")
    custom_ib_info = calculate_initial_balance(valid_processed_data, ib_start_time_str="08:00", ib_end_time_str="09:00")
    sorted_custom_ib_dates = sorted(custom_ib_info.keys())
    for date_key in sorted_custom_ib_dates:
        ib_data = custom_ib_info[date_key]
        print(f"\nDate: {date_key.format_common_iso()}")
        if "error" in ib_data:
            print(f"  Error: {ib_data['error']}")
        elif "message" in ib_data:
             print(f"  Message: {ib_data['message']}")
        else:
            print(f"  IB Start: {ib_data['ib_start_et'].format_common_iso()}")
            print(f"  IB End:   {ib_data['ib_end_et'].format_common_iso()}")
            print(f"  IB High:  {ib_data['ib_high']}")
            print(f"  IB Low:   {ib_data['ib_low']}")

    # Example for is_within_initial_balance utility
    print("\n--- is_within_initial_balance specific test (first valid IB day) ---")
    if sorted_ib_dates:
        first_calc_date = None
        for d in sorted_ib_dates:
            if "error" not in initial_balance_info[d] and "message" not in initial_balance_info[d]:
                first_calc_date = d
                break

        if first_calc_date:
            first_day_ib = initial_balance_info[first_calc_date]
            test_time_inside = first_day_ib['ib_start_et'].add(minutes=5) # whenever add method
            test_time_outside = first_day_ib['ib_end_et'].add(minutes=5)

            print(f"Checking {test_time_inside.format_common_iso()} against IB for {first_calc_date.format_common_iso()}: "
                  f"{is_within_initial_balance(test_time_inside, first_day_ib['ib_start_et'], first_day_ib['ib_end_et'])}")
            print(f"Checking {test_time_outside.format_common_iso()} against IB for {first_calc_date.format_common_iso()}: "
                  f"{is_within_initial_balance(test_time_outside, first_day_ib['ib_start_et'], first_day_ib['ib_end_et'])}")
        else:
            print("Could not find a day with successfully calculated IB for specific test.")
    else:
        print("No IB data calculated to run specific is_within_initial_balance test.")
