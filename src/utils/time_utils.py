import datetime
import pytz

def convert_to_et(dt_object, original_tz_str=None):
    """
    Converts a datetime object to 'America/New_York' (ET).

    Args:
        dt_object (datetime.datetime): The datetime object to convert.
                                      Can be naive or timezone-aware.
        original_tz_str (str, optional): The timezone string (e.g., 'UTC', 'Europe/London')
                                         if dt_object is naive. Defaults to None.

    Returns:
        datetime.datetime: A timezone-aware datetime object in ET.
                           Returns None if conversion is not possible.
    """
    et_tz = pytz.timezone('America/New_York')

    if dt_object.tzinfo is None:
        if original_tz_str:
            try:
                original_tz = pytz.timezone(original_tz_str)
                # Explicitly use is_dst=None to ensure pytz raises NonExistentTimeError or AmbiguousTimeError
                # as per documentation, instead of possibly auto-resolving.
                dt_object = original_tz.localize(dt_object, is_dst=None)
            except pytz.UnknownTimeZoneError:
                # Handle unknown timezone string if necessary
                print(f"Error: Unknown original timezone string: {original_tz_str}")
                return None
            except pytz.exceptions.NonExistentTimeError as e:
                print(f"Error: Naive datetime {dt_object} is non-existent in {original_tz_str} due to DST: {e}")
                return None
            except pytz.exceptions.AmbiguousTimeError as e:
                # For ambiguous times, pytz.localize with is_dst=None resolves it by picking one.
                # This is often the desired behavior (e.g., system default or first occurrence).
                print(f"Warning: Naive datetime {dt_object} is ambiguous in {original_tz_str} due to DST. Attempting to resolve by choosing standard time (is_dst=False). Error: {e}")
                try:
                    # Resolve ambiguity by explicitly choosing one representation (e.g., standard time)
                    dt_object = original_tz.localize(dt_object, is_dst=False)
                except Exception as final_e:
                    print(f"Could not resolve ambiguous time for {dt_object} in {original_tz_str} even after choosing is_dst=False: {final_e}")
                    return None
            # No other exceptions expected here if the above are comprehensive for localization issues.

        else:
            # If dt_object is naive and no original_tz_str is provided,
            # we cannot reliably convert it. It's ambiguous.
            # Depending on policy, one might assume UTC or local system time,
            # but it's safer to require clarification.
            print("Error: Naive datetime provided without an original_tz_str. Conversion is ambiguous.")
            return None

    # If already timezone-aware, or localized above, convert to ET
    return dt_object.astimezone(et_tz)

def get_market_open_close_et(date_obj, open_time_str="09:30", close_time_str="16:00"):
    """
    Calculates the market open and close times in ET for a given date.

    Args:
        date_obj (datetime.date): The date for which to calculate market times.
        open_time_str (str, optional): Market open time "HH:MM". Defaults to "09:30".
        close_time_str (str, optional): Market close time "HH:MM". Defaults to "16:00".

    Returns:
        tuple(datetime.datetime, datetime.datetime): A tuple containing two timezone-aware
                                                     datetime objects (ET): (market_open_et, market_close_et).
                                                     Returns (None, None) if time strings are invalid.
    """
    et_tz = pytz.timezone('America/New_York')

    try:
        open_hour, open_minute = map(int, open_time_str.split(':'))
        close_hour, close_minute = map(int, close_time_str.split(':'))

        if not (0 <= open_hour <= 23 and 0 <= open_minute <= 59 and \
                0 <= close_hour <= 23 and 0 <= close_minute <= 59):
            raise ValueError("Hour or minute out of valid range.")

    except ValueError:
        print(f"Error: Invalid time string format or value. Please use HH:MM with valid ranges. Got: open='{open_time_str}', close='{close_time_str}'")
        return None, None

    # Create naive datetime objects for open and close times
    market_open_naive = datetime.datetime(date_obj.year, date_obj.month, date_obj.day, open_hour, open_minute)
    market_close_naive = datetime.datetime(date_obj.year, date_obj.month, date_obj.day, close_hour, close_minute)

    # Localize these naive datetimes to ET
    # For market times like 9:30 AM or 4:00 PM, DST ambiguity is rare for ET,
    # as transitions usually happen at 2:00 AM.
    # However, using localize is the correct way to ensure timezone awareness.
    try:
        market_open_et = et_tz.localize(market_open_naive)
        market_close_et = et_tz.localize(market_close_naive)
    except (pytz.exceptions.AmbiguousTimeError, pytz.exceptions.NonExistentTimeError) as e:
        # This should be very rare for typical market open/close times in ET
        # but handling it defensively.
        print(f"Warning: DST transition issue for market time on {date_obj}: {e}")
        # Attempt to normalize if ambiguous (e.g. fall-back)
        if isinstance(e, pytz.exceptions.AmbiguousTimeError):
            market_open_et = et_tz.normalize(et_tz.localize(market_open_naive, is_dst=True)) # or is_dst=False
            market_close_et = et_tz.normalize(et_tz.localize(market_close_naive, is_dst=True))
        else: # NonExistentTimeError (e.g. spring-forward)
            # This would mean the chosen HH:MM literally doesn't exist that day.
            # For 9:30 or 16:00 this is practically impossible in ET.
            # Could advance time by an hour for spring-forward if it was, e.g. 2:30 AM
            print(f"Error: Market time {open_time_str} or {close_time_str} is non-existent for {date_obj} in ET.")
            return None, None


    return market_open_et, market_close_et

if __name__ == '__main__':
    # Example Usage:

    # --- convert_to_et examples ---
    print("--- convert_to_et examples ---")
    # 1. Naive datetime, assuming it's UTC
    naive_utc_dt = datetime.datetime(2023, 10, 26, 14, 30) # 2:30 PM UTC
    et_dt_from_utc = convert_to_et(naive_utc_dt, original_tz_str='UTC')
    if et_dt_from_utc:
        print(f"Naive UTC {naive_utc_dt} to ET: {et_dt_from_utc.strftime('%Y-%m-%d %H:%M:%S %Z%z')}") # Expected: 2023-10-26 10:30:00 EDT-0400

    # 2. Naive datetime, assuming it's London time (BST during summer, GMT during winter)
    # London is UTC+1 on this date (BST)
    naive_london_dt = datetime.datetime(2023, 8, 15, 15, 30) # 3:30 PM London time
    et_dt_from_london = convert_to_et(naive_london_dt, original_tz_str='Europe/London')
    if et_dt_from_london:
        print(f"Naive London {naive_london_dt} to ET: {et_dt_from_london.strftime('%Y-%m-%d %H:%M:%S %Z%z')}") # Expected: 2023-08-15 10:30:00 EDT-0400

    # 3. Already timezone-aware datetime (e.g., UTC)
    aware_utc_dt = pytz.utc.localize(datetime.datetime(2023, 11, 5, 14, 30)) # 2:30 PM UTC
    et_dt_from_aware_utc = convert_to_et(aware_utc_dt)
    if et_dt_from_aware_utc:
        print(f"Aware UTC {aware_utc_dt.strftime('%Y-%m-%d %H:%M:%S %Z%z')} to ET: {et_dt_from_aware_utc.strftime('%Y-%m-%d %H:%M:%S %Z%z')}") # Expected: 2023-11-05 09:30:00 EST-0500 (after DST change)

    # 4. Naive datetime with no original timezone (should print error)
    ambiguous_naive_dt = datetime.datetime(2023, 10, 26, 10, 30)
    print(f"Trying to convert naive {ambiguous_naive_dt} without original_tz_str:")
    convert_to_et(ambiguous_naive_dt)

    # 5. DST "fall back" example for original_tz_str (e.g. 'America/New_York')
    # On 2023-11-05, 1:30 AM ET happens twice.
    # pytz.localize by default raises AmbiguousTimeError. Handled in function.
    naive_ambiguous_dt_in_et = datetime.datetime(2023, 11, 5, 1, 30, 0)
    print(f"Naive ambiguous {naive_ambiguous_dt_in_et} (pretending it's ET) to ET:")
    converted_ambiguous = convert_to_et(naive_ambiguous_dt_in_et, original_tz_str='America/New_York')
    if converted_ambiguous:
         print(f"Converted ambiguous ET: {converted_ambiguous.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")

    # 6. DST "spring forward" example for original_tz_str (e.g. 'America/New_York')
    # On 2023-03-12, 2:30 AM ET does not exist.
    # pytz.localize by default raises NonExistentTimeError. Handled in function.
    naive_non_existent_dt_in_et = datetime.datetime(2024, 3, 10, 2, 30, 0) # Spring forward for ET in 2024
    print(f"Naive non-existent {naive_non_existent_dt_in_et} (pretending it's ET) to ET:")
    converted_non_existent = convert_to_et(naive_non_existent_dt_in_et, original_tz_str='America/New_York')
    if converted_non_existent:
        print(f"Converted non-existent ET: {converted_non_existent.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    else:
        print(f"Conversion failed for non-existent time as expected by current simple handling.")


    # --- get_market_open_close_et examples ---
    print("\n--- get_market_open_close_et examples ---")
    # 1. Standard day
    trade_date_summer = datetime.date(2023, 8, 15) # During EDT
    open_summer, close_summer = get_market_open_close_et(trade_date_summer)
    if open_summer and close_summer:
        print(f"Market times for {trade_date_summer}:")
        print(f"Open: {open_summer.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")   # Expected: 2023-08-15 09:30:00 EDT-0400
        print(f"Close: {close_summer.strftime('%Y-%m-%d %H:%M:%S %Z%z')}") # Expected: 2023-08-15 16:00:00 EDT-0400

    # 2. Day after DST ends (becomes EST)
    trade_date_winter = datetime.date(2023, 11, 6) # After fall back to EST
    open_winter, close_winter = get_market_open_close_et(trade_date_winter)
    if open_winter and close_winter:
        print(f"Market times for {trade_date_winter}:")
        print(f"Open: {open_winter.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")   # Expected: 2023-11-06 09:30:00 EST-0500
        print(f"Close: {close_winter.strftime('%Y-%m-%d %H:%M:%S %Z%z')}") # Expected: 2023-11-06 16:00:00 EST-0500

    # 3. Custom market times
    trade_date_custom = datetime.date(2023, 10, 10)
    open_custom, close_custom = get_market_open_close_et(trade_date_custom, open_time_str="08:00", close_time_str="14:30")
    if open_custom and close_custom:
        print(f"Custom market times for {trade_date_custom}:")
        print(f"Open: {open_custom.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        print(f"Close: {close_custom.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")

    # 4. Invalid time string
    print("Testing invalid time string for market open/close:")
    get_market_open_close_et(datetime.date(2023, 1, 1), open_time_str="99:00")

    # Example of a DST transition day itself for market open/close
    # For US markets, DST transitions are typically on Sunday at 2 AM, when markets are closed.
    # So, 9:30 AM / 4:00 PM on a DST transition Sunday (if it were a trading day) would be unambiguous.
    dst_start_2024 = datetime.date(2024, 3, 10) # Spring forward in US
    open_dst_start, close_dst_start = get_market_open_close_et(dst_start_2024)
    if open_dst_start and close_dst_start:
        print(f"Market times for DST start {dst_start_2024}:")
        print(f"Open: {open_dst_start.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")   # 2024-03-10 09:30:00 EDT-0400
        print(f"Close: {close_dst_start.strftime('%Y-%m-%d %H:%M:%S %Z%z')}") # 2024-03-10 16:00:00 EDT-0400

    dst_end_2023 = datetime.date(2023, 11, 5) # Fall back in US
    open_dst_end, close_dst_end = get_market_open_close_et(dst_end_2023)
    if open_dst_end and close_dst_end:
        print(f"Market times for DST end {dst_end_2023}:")
        print(f"Open: {open_dst_end.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")   # 2023-11-05 09:30:00 EST-0500 (after the 1 AM EST repeat)
        print(f"Close: {close_dst_end.strftime('%Y-%m-%d %H:%M:%S %Z%z')}") # 2023-11-05 16:00:00 EST-0500
