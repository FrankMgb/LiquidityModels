import datetime
import pandas as pd # Using pandas for easier data manipulation and timestamp parsing
from src.utils.time_utils import convert_to_et, get_market_open_close_et
import pytz # For creating timezone-aware datetimes in sample data

def load_raw_data():
    """
    Simulates loading raw market data.
    Returns a list of dictionaries, where each dictionary represents a data point (e.g., a candle).
    Timestamps are intentionally varied to test conversion logic.
    """
    sample_data = [
        {
            "timestamp": "2023-10-25 09:30:00", # Assumed to be naive, should be treated as ET if no original_tz given
            "open": 150.00, "high": 150.50, "low": 149.80, "close": 150.20, "volume": 1000
        },
        {
            "timestamp": "2023-10-25 10:00:00 Europe/London", # Timezone info in string
            "open": 150.20, "high": 151.00, "low": 150.10, "close": 150.90, "volume": 1200
        },
        {
            "timestamp": datetime.datetime(2023, 10, 25, 14, 30, 0), # Naive datetime object
            "open": 150.90, "high": 151.20, "low": 150.80, "close": 151.10, "volume": 900
        },
        { # Data for a day with DST change in US (Fall back)
            "timestamp": pytz.utc.localize(datetime.datetime(2023, 11, 5, 5, 30, 0)), # 1:30 AM ET (first instance, EDT)
            "open": 152.00, "high": 152.50, "low": 151.80, "close": 152.20, "volume": 1100
        },
        {
            "timestamp": pytz.utc.localize(datetime.datetime(2023, 11, 5, 6, 30, 0)), # 1:30 AM ET (second instance, EST) by UTC
            "open": 152.10, "high": 152.60, "low": 151.90, "close": 152.30, "volume": 1300
        },
        { # Unix timestamp (seconds since epoch)
            "timestamp": 1678624200, # This is March 12, 2023 08:30 AM New York Time (EDT) - DST Spring Forward Day. (13:30 UTC)
            "open": 155.00, "high": 155.50, "low": 154.80, "close": 155.20, "volume": 1000
        },
         { # ISO format with Z (Zulu/UTC)
            "timestamp": "2023-08-15T13:30:00Z",
            "open": 160.00, "high": 160.50, "low": 159.80, "close": 160.20, "volume": 1000
        },
    ]
    return sample_data

def parse_timestamp(ts_input, original_tz_if_naive=None):
    """
    Parses a variety of timestamp inputs into a timezone-aware datetime object.
    If the input is naive, it's localized to original_tz_if_naive or assumed UTC if not provided.
    """
    if isinstance(ts_input, datetime.datetime):
        dt_obj = ts_input
        # If naive and original_tz_if_naive is given, localize
        if dt_obj.tzinfo is None and original_tz_if_naive:
            try:
                tz = pytz.timezone(original_tz_if_naive)
                dt_obj = tz.localize(dt_obj)
            except Exception as e:
                print(f"Could not localize naive datetime {dt_obj} to {original_tz_if_naive}: {e}")
                return None
        # If still naive (no original_tz_if_naive or already tz-aware but somehow became naive),
        # it's hard to make a good assumption. For this example, we'll try to convert to ET later.
        # Best if datetime objects come in aware or with explicit original_tz_if_naive.
        return dt_obj

    if isinstance(ts_input, (int, float)): # Unix timestamp
        try:
            # Use pandas for robust Unix timestamp conversion, result is UTC-aware
            dt_obj = pd.to_datetime(ts_input, unit='s', utc=True)
            if hasattr(dt_obj, 'to_pydatetime'):
                return dt_obj.to_pydatetime()
            return dt_obj # Should be a datetime object already
        except Exception as e:
            print(f"Error parsing Unix timestamp {ts_input}: {e}")
            return None

    if isinstance(ts_input, str):
        try:
            # Try pandas to_datetime, which is robust
            dt_obj = pd.to_datetime(ts_input)
            # pd.to_datetime might return a Timestamp object, convert to python datetime
            if hasattr(dt_obj, 'to_pydatetime'):
                dt_obj = dt_obj.to_pydatetime()

            # If pandas parsing results in a naive datetime, and original_tz_if_naive is set, localize it.
            # This is common if the string has no explicit timezone info.
            if dt_obj.tzinfo is None and original_tz_if_naive:
                try:
                    tz = pytz.timezone(original_tz_if_naive)
                    # Important: handle AmbiguousTimeError or NonExistentTimeError if localizing
                    dt_obj = tz.localize(dt_obj, is_dst=None) # is_dst=None tries to guess, or use specific
                except pytz.exceptions.AmbiguousTimeError:
                    # Handle ambiguity, e.g., pick one or log error
                    # For now, let convert_to_et handle it if it's still naive and ambiguous for ET
                    print(f"Ambiguous time for naive string {ts_input} with {original_tz_if_naive}. Proceeding with naive.")
                except pytz.exceptions.NonExistentTimeError:
                    print(f"Non-existent time for naive string {ts_input} with {original_tz_if_naive}.")
                    return None # Or handle as error
            return dt_obj
        except Exception as e:
            print(f"Error parsing timestamp string '{ts_input}': {e}")
            return None

    print(f"Unsupported timestamp type: {type(ts_input)}")
    return None


def process_data_timestamps(raw_data, default_original_tz='America/New_York'):
    """
    Processes raw data to standardize timestamps to Eastern Time (ET).

    Args:
        raw_data (list): A list of dictionaries, where each dictionary has a 'timestamp' key.
        default_original_tz (str): The timezone to assume for naive timestamps if no other
                                   timezone information is present in the timestamp itself.
                                   Defaults to 'America/New_York', implying naive times are already ET.

    Returns:
        list: Data with 'timestamp' values converted to timezone-aware ET datetime objects.
              Entries that fail parsing/conversion will have their timestamp set to None.
    """
    processed_data = []
    for record in raw_data:
        new_record = record.copy()
        original_ts = new_record.get("timestamp")

        parsed_dt = None

        if isinstance(original_ts, str):
            # Try to infer timezone from string first if possible (e.g. "Europe/London" suffix)
            # A more robust way would be to use regex or dateutil.parser for complex strings
            parts = original_ts.split(" ")
            potential_tz_str = None
            if len(parts) > 2 and "/" in parts[-1] : # Heuristic: "YYYY-MM-DD HH:MM:SS Timezone/City"
                try:
                    pytz.timezone(parts[-1]) # check if valid tz
                    potential_tz_str = parts[-1]
                    ts_to_parse = " ".join(parts[:-1])
                    parsed_dt = parse_timestamp(ts_to_parse, original_tz_if_naive=potential_tz_str)
                except pytz.UnknownTimeZoneError:
                    parsed_dt = parse_timestamp(original_ts, original_tz_if_naive=default_original_tz)
            else: # Standard parsing
                 parsed_dt = parse_timestamp(original_ts, original_tz_if_naive=default_original_tz)

        elif isinstance(original_ts, datetime.datetime):
            if original_ts.tzinfo is None: # Naive datetime object
                parsed_dt = parse_timestamp(original_ts, original_tz_if_naive=default_original_tz)
            else: # Already timezone-aware
                parsed_dt = original_ts

        elif isinstance(original_ts, (int, float)): # Unix timestamp
            # Unix timestamps are typically UTC. convert_to_et will handle conversion from UTC.
            parsed_dt = parse_timestamp(original_ts) # This will make it UTC aware

        if parsed_dt:
            # If parsed_dt is naive and default_original_tz is America/New_York, convert_to_et will localize it.
            # If parsed_dt is aware (e.g. from Unix (UTC) or string with tz), convert_to_et converts it.
            # If parsed_dt is naive and default_original_tz is something else, convert_to_et will use that.
            new_record['timestamp_et'] = convert_to_et(parsed_dt, original_tz_str=default_original_tz if parsed_dt.tzinfo is None else None)
        else:
            new_record['timestamp_et'] = None
            print(f"Failed to parse or determine timezone for timestamp: {original_ts}")

        processed_data.append(new_record)

    return processed_data

if __name__ == '__main__':
    print("--- Loading Raw Data ---")
    raw_market_data = load_raw_data()
    for i, item in enumerate(raw_market_data):
        print(f"Record {i+1} original timestamp: {item['timestamp']} (type: {type(item['timestamp'])})")

    print("\n--- Processing Data Timestamps (assuming naive are ET) ---")
    # Example: Assume naive timestamps are already in ET.
    # convert_to_et will then localize them correctly.
    processed_market_data_et_naive = process_data_timestamps(raw_market_data, default_original_tz='America/New_York')
    for item in processed_market_data_et_naive:
        if item['timestamp_et']:
            print(f"Original: {item['timestamp']}, Type: {type(item['timestamp'])} -> ET: {item['timestamp_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        else:
            print(f"Original: {item['timestamp']}, Type: {type(item['timestamp'])} -> Failed to convert")

    print("\n--- Processing Data Timestamps (assuming naive are UTC) ---")
    # Example: Assume naive timestamps are in UTC.
    processed_market_data_utc_naive = process_data_timestamps(raw_market_data, default_original_tz='UTC')
    for item in processed_market_data_utc_naive:
        if item['timestamp_et']:
            print(f"Original: {item['timestamp']}, Type: {type(item['timestamp'])} -> ET: {item['timestamp_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        else:
            print(f"Original: {item['timestamp']}, Type: {type(item['timestamp'])} -> Failed to convert")

    # Example with a datetime object that is already ET aware (but pytz object)
    print("\n--- Processing with already ET-aware datetime object ---")
    et_tz = pytz.timezone('America/New_York')
    aware_et_time = et_tz.localize(datetime.datetime(2023, 10, 26, 9, 30, 0))
    custom_data = [{"timestamp": aware_et_time, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 50}]
    processed_custom_data = process_data_timestamps(custom_data, default_original_tz='America/New_York')
    for item in processed_custom_data:
        if item['timestamp_et']:
            print(f"Original: {item['timestamp']} -> ET: {item['timestamp_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        else:
            print(f"Original: {item['timestamp']} -> Failed to convert")

    # Example: Demonstrate get_market_open_close_et
    print("\n--- Market Open/Close Example ---")
    sample_date = datetime.date(2023, 10, 26) # A date where New York is in EDT
    open_time, close_time = get_market_open_close_et(sample_date)
    if open_time and close_time:
        print(f"Market open for {sample_date}: {open_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        print(f"Market close for {sample_date}: {close_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")

    sample_date_dst_end = datetime.date(2023, 11, 5) # DST ends in NY on this day
    open_time_dst, close_time_dst = get_market_open_close_et(sample_date_dst_end)
    if open_time_dst and close_time_dst:
        print(f"Market open for {sample_date_dst_end} (DST end): {open_time_dst.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        print(f"Market close for {sample_date_dst_end} (DST end): {close_time_dst.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")


# --- Initial Balance Logic ---

def calculate_initial_balance(
    processed_data_et,
    ib_start_time_str="09:30",
    ib_end_time_str="10:30",
    market_tz_str='America/New_York'
):
    """
    Calculates the Initial Balance (IB) period's start, end, high, and low for each day.

    Args:
        processed_data_et (list): List of data records, where each record is a dictionary
                                  and has a 'timestamp_et' (timezone-aware datetime in ET)
                                  and 'high', 'low' keys.
        ib_start_time_str (str): IB start time in "HH:MM" format. Defaults to "09:30".
        ib_end_time_str (str): IB end time in "HH:MM" format. Defaults to "10:30".
        market_tz_str (str): Timezone string for the market. Defaults to 'America/New_York'.

    Returns:
        dict: A dictionary where keys are dates (as datetime.date objects) and values are
              dictionaries containing:
              {'ib_start_et', 'ib_end_et', 'ib_high', 'ib_low', 'error' (optional)}
    """
    if not processed_data_et:
        return {}

    daily_ib_data = {}
    market_tz = pytz.timezone(market_tz_str)

    # Group data by date (in ET)
    data_by_date = {}
    for record in processed_data_et:
        if record['timestamp_et']:
            # Ensure timestamp is in the target market_tz for consistent day grouping
            # Though they are already ET, this is a good practice if market_tz_str could vary
            record_date = record['timestamp_et'].astimezone(market_tz).date()
            if record_date not in data_by_date:
                data_by_date[record_date] = []
            data_by_date[record_date].append(record)

    for trade_date, records_for_day in data_by_date.items():
        # Skip weekends (Monday is 0, Sunday is 6)
        if trade_date.weekday() >= 5: # Saturday or Sunday
            daily_ib_data[trade_date] = {"error": "Weekend, IB not calculated."}
            continue

        try:
            ib_start_hour, ib_start_minute = map(int, ib_start_time_str.split(':'))
            ib_end_hour, ib_end_minute = map(int, ib_end_time_str.split(':'))
        except ValueError:
            daily_ib_data[trade_date] = {"error": f"Invalid IB time string format: {ib_start_time_str} or {ib_end_time_str}"}
            continue

        # Create naive datetime objects for IB start and end times for the specific trade_date
        ib_start_naive = datetime.datetime(trade_date.year, trade_date.month, trade_date.day, ib_start_hour, ib_start_minute)
        ib_end_naive = datetime.datetime(trade_date.year, trade_date.month, trade_date.day, ib_end_hour, ib_end_minute)

        # Localize these naive datetimes to the market timezone
        try:
            ib_start_dt_et = market_tz.localize(ib_start_naive, is_dst=None)
            ib_end_dt_et = market_tz.localize(ib_end_naive, is_dst=None)
        except (pytz.exceptions.AmbiguousTimeError, pytz.exceptions.NonExistentTimeError) as e:
            daily_ib_data[trade_date] = {"error": f"DST issue for IB time on {trade_date}: {e}"}
            continue

        # Filter records within the IB period for the current day
        ib_period_records = []
        for record in records_for_day:
            ts_et = record['timestamp_et']
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

        # Calculate high and low for the IB period
        ib_high = max(r['high'] for r in ib_period_records if 'high' in r and r['high'] is not None)
        ib_low = min(r['low'] for r in ib_period_records if 'low' in r and r['low'] is not None)

        daily_ib_data[trade_date] = {
            "ib_start_et": ib_start_dt_et,
            "ib_end_et": ib_end_dt_et,
            "ib_high": ib_high,
            "ib_low": ib_low
        }

    return daily_ib_data

def is_within_initial_balance(timestamp_et, ib_start_et, ib_end_et):
    """
    Checks if a given timestamp falls within the Initial Balance period.

    Args:
        timestamp_et (datetime.datetime): The timezone-aware ET timestamp to check.
        ib_start_et (datetime.datetime): The timezone-aware ET start of the IB period.
        ib_end_et (datetime.datetime): The timezone-aware ET end of the IB period.

    Returns:
        bool: True if the timestamp is within the IB period, False otherwise.
    """
    if not isinstance(timestamp_et, datetime.datetime) or timestamp_et.tzinfo is None:
        # Or raise an error, or try to convert it if a policy is defined
        print("Warning: is_within_initial_balance expects a timezone-aware ET datetime for timestamp_et.")
        return False
    if not isinstance(ib_start_et, datetime.datetime) or ib_start_et.tzinfo is None:
        print("Warning: is_within_initial_balance expects a timezone-aware ET datetime for ib_start_et.")
        return False
    if not isinstance(ib_end_et, datetime.datetime) or ib_end_et.tzinfo is None:
        print("Warning: is_within_initial_balance expects a timezone-aware ET datetime for ib_end_et.")
        return False

    return ib_start_et <= timestamp_et < ib_end_et


if __name__ == '__main__':
    print("--- Loading Raw Data ---")
    raw_market_data = load_raw_data()
    # for i, item in enumerate(raw_market_data):
    #     print(f"Record {i+1} original timestamp: {item['timestamp']} (type: {type(item['timestamp'])})")

    print("\n--- Processing Data Timestamps (assuming naive are ET by default) ---")
    processed_market_data = process_data_timestamps(raw_market_data) # default_original_tz='America/New_York'
    # for item in processed_market_data:
    #     if item['timestamp_et']:
    #         print(f"Original: {item['timestamp']} -> ET: {item['timestamp_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    #     else:
    #         print(f"Original: {item['timestamp']} -> Failed to convert")

    print("\n--- Calculating Initial Balance (9:30 AM - 10:30 AM ET) ---")
    # Filter out records where timestamp_et might be None due to conversion errors
    valid_processed_data = [r for r in processed_market_data if r['timestamp_et'] is not None]

    initial_balance_info = calculate_initial_balance(valid_processed_data)
    for date_key, ib_data in sorted(initial_balance_info.items()):
        print(f"\nDate: {date_key.strftime('%Y-%m-%d')}")
        if "error" in ib_data:
            print(f"  Error: {ib_data['error']}")
        elif "message" in ib_data:
            print(f"  IB Start: {ib_data['ib_start_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
            print(f"  IB End:   {ib_data['ib_end_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
            print(f"  Message: {ib_data['message']}")
        else:
            print(f"  IB Start: {ib_data['ib_start_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
            print(f"  IB End:   {ib_data['ib_end_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
            print(f"  IB High:  {ib_data['ib_high']}")
            print(f"  IB Low:   {ib_data['ib_low']}")

            # Example usage of is_within_initial_balance
            if valid_processed_data and valid_processed_data[0]['timestamp_et']:
                ts_to_check = valid_processed_data[0]['timestamp_et']
                # Need to find the IB start/end for the specific day of ts_to_check
                check_date_ib_info = initial_balance_info.get(ts_to_check.date())
                if check_date_ib_info and 'ib_start_et' in check_date_ib_info:
                    is_in_ib = is_within_initial_balance(ts_to_check,
                                                         check_date_ib_info['ib_start_et'],
                                                         check_date_ib_info['ib_end_et'])
                    print(f"  Timestamp {ts_to_check.strftime('%H:%M:%S %Z%z')} on {ts_to_check.date()} within its IB? {is_in_ib}")


    print("\n--- Calculating Initial Balance (Custom 10:00 AM - 11:00 AM ET) ---")
    custom_ib_info = calculate_initial_balance(valid_processed_data, ib_start_time_str="10:00", ib_end_time_str="11:00")
    for date_key, ib_data in sorted(custom_ib_info.items()):
        print(f"\nDate: {date_key.strftime('%Y-%m-%d')}")
        if "error" in ib_data:
            print(f"  Error: {ib_data['error']}")
        elif "message" in ib_data:
             print(f"  Message: {ib_data['message']}")
        else:
            print(f"  IB Start: {ib_data['ib_start_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
            print(f"  IB End:   {ib_data['ib_end_et'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
            print(f"  IB High:  {ib_data['ib_high']}")
            print(f"  IB Low:   {ib_data['ib_low']}")

    # Example for is_within_initial_balance utility
    print("\n--- is_within_initial_balance specific test ---")
    if initial_balance_info:
        first_day_date = sorted(initial_balance_info.keys())[0]
        first_day_ib = initial_balance_info[first_day_date]

        if "ib_start_et" in first_day_ib: # Check if IB was calculated successfully
            test_time_inside = first_day_ib['ib_start_et'] + datetime.timedelta(minutes=5)
            test_time_outside = first_day_ib['ib_end_et'] + datetime.timedelta(minutes=5)

            print(f"Checking {test_time_inside.strftime('%H:%M:%S %Z%z')} against IB for {first_day_date}: "
                  f"{is_within_initial_balance(test_time_inside, first_day_ib['ib_start_et'], first_day_ib['ib_end_et'])}")
            print(f"Checking {test_time_outside.strftime('%H:%M:%S %Z%z')} against IB for {first_day_date}: "
                  f"{is_within_initial_balance(test_time_outside, first_day_ib['ib_start_et'], first_day_ib['ib_end_et'])}")
        else:
            print(f"Could not run is_within_initial_balance test for {first_day_date} as IB data is missing or has error.")

    # Example of data that might not fall into IB
    sparse_data = [
        {"timestamp_et": convert_to_et(datetime.datetime(2023, 10, 25, 8, 0, 0), 'America/New_York'), "high": 100, "low": 99}, # Before IB
        {"timestamp_et": convert_to_et(datetime.datetime(2023, 10, 25, 11, 0, 0), 'America/New_York'), "high": 102, "low": 101},# After IB
    ]
    print("\n--- Calculating Initial Balance with sparse data (no data in IB) ---")
    sparse_ib_info = calculate_initial_balance(sparse_data)
    for date_key, ib_data in sorted(sparse_ib_info.items()):
        print(f"\nDate: {date_key.strftime('%Y-%m-%d')}")
        if "message" in ib_data:
            print(f"  Message: {ib_data['message']}")
            print(f"  IB High: {ib_data['ib_high']}") # Should be None
            print(f"  IB Low: {ib_data['ib_low']}")   # Should be None
        elif "error" in ib_data:
            print(f"  Error: {ib_data['error']}")

    # Example for a weekend day
    weekend_data = [
        {"timestamp_et": convert_to_et(datetime.datetime(2023, 10, 28, 9, 35, 0), 'America/New_York'), "high": 100, "low": 99} # A Saturday
    ]
    print("\n--- Calculating Initial Balance for a weekend day ---")
    weekend_ib_info = calculate_initial_balance(weekend_data)
    for date_key, ib_data in sorted(weekend_ib_info.items()):
        print(f"\nDate: {date_key.strftime('%Y-%m-%d')}")
        if "error" in ib_data:
            print(f"  Error: {ib_data['error']}") # Expected: Weekend error
        else:
            print("  IB data unexpectedly found for weekend.")
