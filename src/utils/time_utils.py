import whenever
import pandas as pd # Keep for initial flexible string parsing
from datetime import datetime as std_datetime, date as std_date, time as std_time, timezone as std_timezone # For type hints and conversion from pandas

# Define the target timezone string and ZoneInfo object
TARGET_TZ_STR = "America/New_York" # String identifier
NY_ZONEINFO = whenever.ZoneInfo(TARGET_TZ_STR) # whenever.ZoneInfo object for direct use

# Key ICT Time Level Constants (using whenever.Time for precision)
# These represent wall times in New York.
MARKET_OPEN_ET_TIME = whenever.Time(9, 30)
IB_END_ET_TIME = whenever.Time(10, 30) # Initial Balance end
MIDNIGHT_OPEN_ET_TIME = whenever.Time(0, 0)
NEWS_EMBARGO_ET_TIME = whenever.Time(8, 30)
FOUR_HOUR_CANDLE_ET_1_TIME = whenever.Time(10, 0)
FOUR_HOUR_CANDLE_ET_2_TIME = whenever.Time(14, 0) # 2 PM

# Killzone Time Constants (ET wall times)
ASIAN_KILLZONE_START_TIME = whenever.Time(20, 0)  # 8:00 PM ET
ASIAN_KILLZONE_END_TIME = whenever.Time(22, 0)    # 10:00 PM ET

LONDON_KILLZONE_START_TIME = whenever.Time(2, 0)  # 2:00 AM ET
LONDON_KILLZONE_END_TIME = whenever.Time(5, 0)    # 5:00 AM ET

NY_KILLZONE_START_TIME = whenever.Time(7, 0)      # 7:00 AM ET
NY_KILLZONE_END_TIME = whenever.Time(9, 0)        # 9:00 AM ET

# LONDON_CLOSE_KILLZONE_START_TIME was defined in the plan, ensuring it's here.
LONDON_CLOSE_KILLZONE_START_TIME = whenever.Time(10, 0) # 10:00 AM ET
LONDON_CLOSE_KILLZONE_END_TIME = whenever.Time(12, 0)   # 12:00 PM ET

# Weekly Open Time Constant
WEEKLY_OPEN_SUNDAY_TIME = whenever.Time(18, 0)    # Sunday 6:00 PM ET


def convert_to_et(timestamp_input: any, original_tz_str: str | None = None) -> whenever.ZonedDateTime | None:
    """
    Converts a given timestamp input to a whenever.ZonedDateTime in 'America/New_York' (ET).

    Args:
        timestamp_input: The timestamp to convert. Can be:
            - whenever.Instant
            - whenever.ZonedDateTime
            - whenever.PlainDateTime
            - Python datetime.datetime
            - int/float (Unix timestamp in seconds)
            - str (various formats, including ISO8601 or common datetime strings)
        original_tz_str (str, optional): The timezone string (e.g., 'UTC', 'Europe/London')
                                         to assume if timestamp_input is a naive Python datetime
                                         or a plain string without timezone info.
                                         If None for naive inputs, ambiguity cannot be resolved.

    Returns:
        whenever.ZonedDateTime: A timezone-aware datetime object in ET.
                                Returns None if conversion is not possible or input is invalid.
                                Raises whenever.SkippedTime or whenever.RepeatedTime if a PlainDateTime
                                with original_tz_str results in a non-existent or ambiguous time
                                and 'raise' is the effective disambiguation strategy.
    """
    try:
        # 1. Handle whenever native types
        if isinstance(timestamp_input, whenever.Instant):
            return timestamp_input.to_tz(NY_ZONEINFO)
        if isinstance(timestamp_input, whenever.ZonedDateTime):
            if timestamp_input.tz.name == TARGET_TZ_STR: # Compare by name for robustness
                return timestamp_input
            return timestamp_input.to_tz(NY_ZONEINFO)
        if isinstance(timestamp_input, whenever.PlainDateTime):
            if not original_tz_str:
                print(f"Error: whenever.PlainDateTime provided without original_tz_str. Ambiguous conversion for {timestamp_input}.")
                return None
            # This will raise SkippedTime or RepeatedTime if ambiguous and disambiguate='raise' (default for assume_tz)
            # For our purpose, we want to know if the original_tz makes it invalid, so 'raise' is good.
                return timestamp_input.assume_tz(original_tz_str, disambiguate='raise').to_tz(NY_ZONEINFO)

        # 2. Handle Python datetime.datetime
        if isinstance(timestamp_input, std_datetime):
            py_dt = timestamp_input
            if py_dt.tzinfo is None: # Naive Python datetime
                if not original_tz_str:
                    print(f"Error: Naive Python datetime provided without original_tz_str. Ambiguous conversion for {py_dt}.")
                    return None
                plain_dt = whenever.PlainDateTime.from_py_datetime(py_dt)
                # This will use disambiguate='raise' by default if not specified,
                # or we can be explicit. 'raise' helps identify invalid naive times.
                return plain_dt.assume_tz(original_tz_str, disambiguate='raise').to_tz(NY_ZONEINFO)
            else: # Aware Python datetime
                # Convert aware Python datetime to whenever.Instant first, then to ZonedDateTime
                # Note: whenever.Instant.from_py_datetime expects UTC or raises error if tz is not ZoneInfo UTC.
                # A more general path for aware py_dt is to convert to its UTC equivalent instant.
                # If it has ZoneInfo, ZonedDateTime.from_py_datetime(py_dt).to_tz(NY_ZONEINFO) is better.
                if isinstance(py_dt.tzinfo, type(std_timezone.utc)): # Check if it's stdlib UTC
                     instant = whenever.Instant.from_py_datetime(py_dt)
                     return instant.to_tz(NY_ZONEINFO)
                try:
                    # Attempt to convert directly if tzinfo is ZoneInfo (used by whenever)
                    # This requires py_dt.tzinfo to be a zoneinfo.ZoneInfo object.
                    # If pandas parsed a string with tz, it might be zoneinfo.
                    zdt = whenever.ZonedDateTime.from_py_datetime(py_dt)
                    return zdt.to_tz(NY_ZONEINFO)
                except ValueError: # Likely if tzinfo is not what whenever expects (e.g. pytz)
                    # Fallback: convert to UTC instant then to target TZ
                    utc_py_dt = py_dt.astimezone(std_timezone.utc)
                    instant = whenever.Instant.from_py_datetime(utc_py_dt)
                    return instant.to_tz(NY_ZONEINFO)


        # 3. Handle Unix timestamp (int/float)
        if isinstance(timestamp_input, (int, float)):
            return whenever.Instant.from_timestamp(int(timestamp_input)).to_tz(NY_ZONEINFO)

        # 4. Handle string inputs
        if isinstance(timestamp_input, str):
            s = timestamp_input
            # Attempt 1: Direct ISO parsing by whenever (for UTC or fixed offset strings)
            try:
                # Heuristic: Check if it looks like an ISO string with offset/Z
                # A more robust check might involve trying both parsers if one fails.
                if 'Z' in s or '+' in s or (s.count('-') >= 3 and s[10:].count('-') > 0 and s[10:].startswith("-")): # crude check for offset like -04:00
                    # Try OffsetDateTime first as it's more specific for offsets than Instant's ISO
                    try:
                        odt = whenever.OffsetDateTime.parse_common_iso(s)
                        return odt.to_tz(NY_ZONEINFO)
                    except ValueError: # If not OffsetDateTime ISO, try Instant ISO (for Z)
                        instant = whenever.Instant.parse_common_iso(s)
                        return instant.to_tz(NY_ZONEINFO)
            except ValueError:
                pass # Fall through if not a direct ISO parse by whenever

            # Attempt 2: Check for "datetime_string Timezone/Name" pattern
            parts = s.split(" ")
            potential_tz_name_from_string = None
            datetime_part_str = s # Default to full string if no TZ part found

            if len(parts) > 1:
                # Heuristic: last part contains '/' and first component of TZ is not all digits
                # e.g. "Europe/London" not "10/11" from "10/11/2023"
                last_part = parts[-1]
                if "/" in last_part and not last_part.split('/')[0].isdigit():
                    try:
                        # Validate if it's a known timezone by trying to use it with a dummy date
                        # This is a bit heavy but ensures it's a valid IANA name known to `whenever`
                        whenever.Date(2000,1,1).at(whenever.Time(0,0)).assume_tz(last_part, disambiguate='raise')
                        potential_tz_name_from_string = last_part
                        datetime_part_str = " ".join(parts[:-1])
                    except (whenever.TimeZoneNotFoundError, ValueError, TypeError):
                        potential_tz_name_from_string = None # Not a valid TZ name

            # Attempt 3: Use pandas for flexible parsing of the (potentially shortened) datetime_part_str
            try:
                # Ensure pandas doesn't try to infer timezone from ambiguous strings like "Europe/London"
                # by parsing only the datetime_part_str.
                py_dt_from_pd = pd.to_datetime(datetime_part_str).to_pydatetime()

                # Determine the original_tz for this py_dt_from_pd
                # Priority: 1. From string split, 2. From function arg, 3. Default for naive strings
                final_original_tz_for_conversion = original_tz_str # From function args
                if potential_tz_name_from_string:
                    final_original_tz_for_conversion = potential_tz_name_from_string
                elif py_dt_from_pd.tzinfo is None and not final_original_tz_for_conversion:
                    # If still naive and no TZ info from string or args, assume TARGET_TZ_STR
                    final_original_tz_for_conversion = TARGET_TZ_STR

                # Now convert py_dt_from_pd using final_original_tz_for_conversion
                # This recursive call handles the py_datetime object correctly.
                return convert_to_et(py_dt_from_pd, original_tz_str=final_original_tz_for_conversion)

            except ValueError as e_pd:
                print(f"Error: Pandas could not parse string timestamp '{datetime_part_str}' (derived from '{s}'): {e_pd}")
                return None
            except Exception as e_general_str_parse: # Catch other errors during this string parsing block
                print(f"Error processing string timestamp '{s}': {e_general_str_parse}")
                return None

        print(f"Error: Unsupported timestamp input type: {type(timestamp_input)}")
        return None

    except (whenever.SkippedTime, whenever.RepeatedTime) as e_dst:
        print(f"Error: DST transition issue for input {timestamp_input} (orig_tz: {original_tz_str}). Time is non-existent or ambiguous: {e_dst}")
        return None
    except whenever.TimeZoneNotFoundError as e_tz_not_found:
        print(f"Error: Timezone not found: {e_tz_not_found}")
        return None
    except ValueError as e_val: # Catch other ValueErrors from whenever constructors/methods
        print(f"Error: Value error during conversion for {timestamp_input}: {e_val}")
        return None
    except Exception as e_general: # Catch-all for unexpected issues
        print(f"An unexpected error occurred converting {timestamp_input}: {e_general}")
        return None


def get_market_open_close_et(
    date_input: any, # whenever.Date | std_date
    open_time: whenever.Time = MARKET_OPEN_ET_TIME,
    close_time: whenever.Time = whenever.Time(16,0) # Default market close 4 PM ET
) -> tuple[whenever.ZonedDateTime | None, whenever.ZonedDateTime | None]:
    """
    Calculates the market open and close times as whenever.ZonedDateTime objects in ET.

    Args:
        date_input: The date for which to calculate market times.
                    Can be a whenever.Date or Python datetime.date.
        open_time_str (str): Market open time "HH:MM". Defaults to "09:30".
        close_time_str (str): Market close time "HH:MM". Defaults to "16:00".

    Returns:
        tuple(whenever.ZonedDateTime | None, whenever.ZonedDateTime | None):
            (market_open_et, market_close_et).
            Returns (None, None) if time strings are invalid or other errors occur.
    """
    try:
        if isinstance(date_input, std_date) and not isinstance(date_input, std_datetime):
            w_date = whenever.Date.from_py_date(date_input)
        elif isinstance(date_input, whenever.Date):
            w_date = date_input
        else:
            print(f"Error: Invalid date_input type: {type(date_input)}. Expected whenever.Date or datetime.date.")
            return None, None

        # Construct ZonedDateTime directly using whenever.Time objects
        # 'raise' is safer to ensure the exact time is valid.
        market_open_et = NY_ZONEINFO.convert(w_date.at(open_time), disambiguate='raise')
        market_close_et = NY_ZONEINFO.convert(w_date.at(close_time), disambiguate='raise')

        return market_open_et, market_close_et

    except (ValueError, TypeError) as e_parse: # Catches errors from at() or convert()
        print(f"Error creating ZonedDateTime for market open/close: {e_parse}")
        return None, None
    except (whenever.SkippedTime, whenever.RepeatedTime) as e_dst:
        # This would be rare for typical market hours but good to catch.
        print(f"Error: DST transition issue for market time on {w_date.format_common_iso() if 'w_date' in locals() else 'unknown date'}: {e_dst}")
        return None, None
    except whenever.TimeZoneNotFoundError: # Should not happen with NY_ZONEINFO
        print(f"Error: Timezone '{TARGET_TZ_STR}' not found. This should not occur.")
        return None, None
    except Exception as e_general:
        print(f"An unexpected error in get_market_open_close_et: {e_general}")
        return None, None


if __name__ == '__main__':
    print("--- whenever time_utils examples ---")

    # Example 1: Naive Python datetime, assume UTC
    naive_py_dt_utc = std_datetime(2023, 10, 26, 14, 30) # 2:30 PM UTC
    et_dt1 = convert_to_et(naive_py_dt_utc, original_tz_str='UTC')
    if et_dt1:
        print(f"Naive Py datetime (UTC) {naive_py_dt_utc} -> ET: {et_dt1.format_common_iso()} ({et_dt1.tz})")
        # Expected: 2023-10-26T10:30:00-04:00[America/New_York]

    # Example 2: Aware Python datetime (UTC)
    aware_py_dt_utc = std_datetime(2023, 11, 5, 14, 30, tzinfo=std_timezone.utc) # 2:30 PM UTC
    et_dt2 = convert_to_et(aware_py_dt_utc)
    if et_dt2:
        print(f"Aware Py datetime (UTC) {aware_py_dt_utc} -> ET: {et_dt2.format_common_iso()} ({et_dt2.tz})")
        # Expected: 2023-11-05T09:30:00-05:00[America/New_York] (EST)

    # Example 3: Unix timestamp
    unix_ts = 1678624200 # This is March 12, 2023 08:30 AM ET (EDT)
    et_dt3 = convert_to_et(unix_ts)
    if et_dt3:
        print(f"Unix timestamp {unix_ts} -> ET: {et_dt3.format_common_iso()} ({et_dt3.tz})")
        # Expected: 2023-03-12T08:30:00-04:00[America/New_York]

    # Example 4: ISO String (UTC)
    iso_str_utc = "2023-08-15T13:30:00Z"
    et_dt4 = convert_to_et(iso_str_utc)
    if et_dt4:
        print(f"ISO string (UTC) '{iso_str_utc}' -> ET: {et_dt4.format_common_iso()} ({et_dt4.tz})")
        # Expected: 2023-08-15T09:30:00-04:00[America/New_York]

    # Example 5: ISO String with offset
    iso_str_offset = "2023-08-15T15:30:00+02:00" # e.g. CEST
    et_dt5 = convert_to_et(iso_str_offset)
    if et_dt5:
        print(f"ISO string (offset) '{iso_str_offset}' -> ET: {et_dt5.format_common_iso()} ({et_dt5.tz})")
        # 15:30+02:00 is 13:30 UTC -> 09:30 ET (EDT)
        # Expected: 2023-08-15T09:30:00-04:00[America/New_York]

    # Example 6: Plain string, assume original_tz_str is 'Europe/London'
    plain_str_london = "2023-10-29 01:30:00" # This is ambiguous in London (DST end)
    print(f"\nPlain string '{plain_str_london}', assume 'Europe/London':")
    et_dt6_earlier = convert_to_et(whenever.PlainDateTime.parse_common_iso(plain_str_london).assume_tz("Europe/London", disambiguate="earlier"))
    if et_dt6_earlier:
         print(f"  (earlier) -> ET: {et_dt6_earlier.format_common_iso()} ({et_dt6_earlier.tz})")
    et_dt6_later = convert_to_et(whenever.PlainDateTime.parse_common_iso(plain_str_london).assume_tz("Europe/London", disambiguate="later"))
    if et_dt6_later:
         print(f"  (later)   -> ET: {et_dt6_later.format_common_iso()} ({et_dt6_later.tz})")
    print("  (raise - should print error and return None):")
    et_dt6_raise = convert_to_et(whenever.PlainDateTime.from_py_datetime(std_datetime.strptime(plain_str_london, "%Y-%m-%d %H:%M:%S")), original_tz_str="Europe/London") # default disambiguate='raise'
    if et_dt6_raise:
        print(f"  (raise)   -> ET: {et_dt6_raise.format_common_iso()} ({et_dt6_raise.tz})")
    else:
        print(f"  (raise)   -> Conversion returned None as expected or printed error.")


    # Example 7: Naive string, assume ET (TARGET_TZ)
    naive_str_et = "2023-11-05 01:30:00" # Ambiguous in ET
    print(f"\nNaive string '{naive_str_et}', assume ET (default original_tz for string):")
    # Test convert_to_et with string directly, it should assume TARGET_TZ if original_tz_str is None
    et_dt7 = convert_to_et(naive_str_et) # original_tz_str=None, so convert_to_et assumes TARGET_TZ for naive strings
    if et_dt7: # This will pick one due to pandas->py_datetime->PlainDateTime->assume_tz(TARGET_TZ, disambiguate='raise')
                # which will actually raise because convert_to_et calls itself with TARGET_TZ.
        print(f"  -> ET: {et_dt7.format_common_iso()} ({et_dt7.tz})")
    else:
        print(f"  -> Conversion returned None or printed error (expected for ambiguous if disamb='raise').")


    # Example 8: Non-existent time (spring forward)
    non_existent_str = "2024-03-10 02:30:00" # Does not exist in ET
    print(f"\nNon-existent string '{non_existent_str}', assume ET:")
    et_dt8 = convert_to_et(non_existent_str) # Should use TARGET_TZ, disambiguate='raise'
    if et_dt8:
        print(f"  -> ET: {et_dt8.format_common_iso()} ({et_dt8.tz})")
    else:
        print(f"  -> Conversion returned None or printed error (expected for non-existent).")

    # --- get_market_open_close_et examples ---
    print("\n--- get_market_open_close_et examples ---")
    date_summer = whenever.Date(2023, 8, 15) # During EDT
    open_s, close_s = get_market_open_close_et(date_summer)
    if open_s and close_s:
        print(f"Market times for {date_summer.format_common_iso()}: Open: {open_s.format_common_iso()}, Close: {close_s.format_common_iso()}")

    date_winter = whenever.Date(2023, 11, 6) # During EST
    open_w, close_w = get_market_open_close_et(date_winter)
    if open_w and close_w:
        print(f"Market times for {date_winter.format_common_iso()}: Open: {open_w.format_common_iso()}, Close: {close_w.format_common_iso()}")

    # Test DST transition day for market open (spring forward)
    date_dst_start = whenever.Date(2024, 3, 10)
    print(f"\nMarket open/close for DST start {date_dst_start.format_common_iso()}:")
    op, cl = get_market_open_close_et(date_dst_start)
    if op and cl:
        print(f"  Open: {op.format_common_iso()}, Close: {cl.format_common_iso()}")

    # Test DST transition day for market open (fall back)
    date_dst_end = whenever.Date(2023, 11, 5) # Ambiguous hour 1-2 AM
    print(f"\nMarket open/close for DST end {date_dst_end.format_common_iso()}:")
    op_e, cl_e = get_market_open_close_et(date_dst_end)
    if op_e and cl_e: # 9:30 AM is not ambiguous
        print(f"  Open: {op_e.format_common_iso()}, Close: {cl_e.format_common_iso()}")

    # Test invalid time string
    print("\nMarket open/close with invalid time string:")
    op_inv, cl_inv = get_market_open_close_et(whenever.Date(2023,1,1), open_time_str="99:00")
    if not op_inv and not cl_inv:
        print("  Correctly returned None for invalid time string.")

    # Test with datetime.date input
    py_date_input = std_date(2023, 7, 1)
    print(f"\nMarket open/close for Python date {py_date_input}:")
    op_pyd, cl_pyd = get_market_open_close_et(py_date_input)
    if op_pyd and cl_pyd:
        print(f"  Open: {op_pyd.format_common_iso()}, Close: {cl_pyd.format_common_iso()}")

    # --- Test Time Window Check Functions ---
    print("\n--- Time Window Check Function Examples ---")
    test_date_dst = whenever.Date(2024, 3, 10) # Spring forward EDT
    test_date_std = whenever.Date(2024, 1, 10) # Standard time EST

    # Test time for Initial Balance: 9:45 AM ET
    dt_ib_test = NY_ZONEINFO.convert(test_date_dst.at(9, 45))
    print(f"Is {dt_ib_test.format_common_iso()} within Initial Balance (9:30-10:30 ET)? {is_within_initial_balance_period(dt_ib_test)}")

    # Test time for NY Killzone: 7:30 AM ET
    dt_nykz_test = NY_ZONEINFO.convert(test_date_std.at(7, 30))
    print(f"Is {dt_nykz_test.format_common_iso()} within NY Killzone (7-9 ET)? {is_within_ny_killzone(dt_nykz_test)}")
    dt_nykz_test_outside = NY_ZONEINFO.convert(test_date_std.at(9, 30))
    print(f"Is {dt_nykz_test_outside.format_common_iso()} within NY Killzone (7-9 ET)? {is_within_ny_killzone(dt_nykz_test_outside)}")


    # Test time for London Killzone: 3:00 AM ET
    dt_ldnkz_test = NY_ZONEINFO.convert(test_date_dst.at(3, 0))
    print(f"Is {dt_ldnkz_test.format_common_iso()} within London Killzone (2-5 ET)? {is_within_london_killzone(dt_ldnkz_test)}")

    # Test time for London Close Killzone: 10:30 AM ET
    dt_ldnclosekz_test = NY_ZONEINFO.convert(test_date_std.at(10, 30))
    print(f"Is {dt_ldnclosekz_test.format_common_iso()} within London Close KZ (10-12 ET)? {is_within_london_close_killzone(dt_ldnclosekz_test)}")

    # Test time for Asian Killzone: 8:30 PM ET
    dt_asiankz_test = NY_ZONEINFO.convert(test_date_dst.at(20, 30)) # 8:30 PM
    print(f"Is {dt_asiankz_test.format_common_iso()} within Asian Killzone (8PM-10PM ET)? {is_within_asian_killzone(dt_asiankz_test)}")
    dt_asiankz_test_outside = NY_ZONEINFO.convert(test_date_dst.at(19, 0)) # 7:00 PM
    print(f"Is {dt_asiankz_test_outside.format_common_iso()} within Asian Killzone (8PM-10PM ET)? {is_within_asian_killzone(dt_asiankz_test_outside)}")


    # Test for is_within_macro_time: 9:50 AM - 10:10 AM ET
    macro_start = whenever.Time(9, 50)
    macro_end = whenever.Time(10, 10)
    dt_macro_inside = NY_ZONEINFO.convert(test_date_std.at(10, 0))
    dt_macro_outside = NY_ZONEINFO.convert(test_date_std.at(10, 15))
    print(f"Is {dt_macro_inside.format_common_iso()} within Macro Time (9:50-10:10 ET)? {is_within_macro_time(dt_macro_inside, macro_start, macro_end)}")
    print(f"Is {dt_macro_outside.format_common_iso()} within Macro Time (9:50-10:10 ET)? {is_within_macro_time(dt_macro_outside, macro_start, macro_end)}")

    # --- Test Data-Dependent Price Retrieval Functions ---
    print("\n--- Data-Dependent Price Retrieval Function Examples ---")

    # Sample OHLC DataFrame (1-minute data, America/New_York ZonedDateTimes)
    sample_dates = [
        # Sunday, Jan 7, 2024 (for weekly open)
        NY_ZONEINFO.convert(whenever.Date(2024, 1, 7).at(18, 0)), # Sun 6:00 PM ET - Weekly Open
        NY_ZONEINFO.convert(whenever.Date(2024, 1, 7).at(18, 1)),
        # Monday, Jan 8, 2024
        NY_ZONEINFO.convert(whenever.Date(2024, 1, 8).at(0, 0)),  # Midnight Open
        NY_ZONEINFO.convert(whenever.Date(2024, 1, 8).at(0, 1)),
        NY_ZONEINFO.convert(whenever.Date(2024, 1, 8).at(9, 29)),
        NY_ZONEINFO.convert(whenever.Date(2024, 1, 8).at(9, 30)),  # NYSE Open
        NY_ZONEINFO.convert(whenever.Date(2024, 1, 8).at(9, 31)),
        # Tuesday, Jan 9, 2024
        NY_ZONEINFO.convert(whenever.Date(2024, 1, 9).at(0, 0)), # Midnight Open for Tuesday
        NY_ZONEINFO.convert(whenever.Date(2024, 1, 9).at(9, 30)), # NYSE Open for Tuesday
    ]
    sample_data = {
        'timestamp': sample_dates,
        'open': [100.00, 100.10, # Sunday
                 101.00, 101.05, # Monday Midnight
                 102.00, 102.50, 102.55, # Monday NYSE Open
                 103.00, 103.50], # Tuesday
        'high': [d + 0.5 for d in [100.00, 100.10, 101.00, 101.05, 102.00, 102.50, 102.55, 103.00, 103.50]],
        'low': [d - 0.5 for d in [100.00, 100.10, 101.00, 101.05, 102.00, 102.50, 102.55, 103.00, 103.50]],
        'close': [d + 0.2 for d in [100.00, 100.10, 101.00, 101.05, 102.00, 102.50, 102.55, 103.00, 103.50]],
    }
    sample_ohlc_df = pd.DataFrame(sample_data)

    date_mon = whenever.Date(2024, 1, 8)
    date_tue = whenever.Date(2024, 1, 9)

    # Test get_midnight_open_price_for_day
    price_midnight_mon = get_midnight_open_price_for_day(date_mon, sample_ohlc_df)
    print(f"Midnight Open Price for {date_mon.format_common_iso()}: {price_midnight_mon}") # Expected: 101.00
    price_midnight_tue = get_midnight_open_price_for_day(date_tue, sample_ohlc_df)
    print(f"Midnight Open Price for {date_tue.format_common_iso()}: {price_midnight_tue}") # Expected: 103.00

    # Test get_nyse_open_price_for_day
    price_nyse_open_mon = get_nyse_open_price_for_day(date_mon, sample_ohlc_df)
    print(f"NYSE Open Price for {date_mon.format_common_iso()}: {price_nyse_open_mon}") # Expected: 102.50
    price_nyse_open_tue = get_nyse_open_price_for_day(date_tue, sample_ohlc_df) # Expected: 103.50
    print(f"NYSE Open Price for {date_tue.format_common_iso()}: {price_nyse_open_tue}")


    # Test get_weekly_open_price_for_week
    # For Monday Jan 8
    weekly_open_mon = get_weekly_open_price_for_week(date_mon, sample_ohlc_df)
    print(f"Weekly Open Price relevant for {date_mon.format_common_iso()}: {weekly_open_mon}") # Expected: 100.00
    # For Tuesday Jan 9
    weekly_open_tue = get_weekly_open_price_for_week(date_tue, sample_ohlc_df)
    print(f"Weekly Open Price relevant for {date_tue.format_common_iso()}: {weekly_open_tue}") # Expected: 100.00
    # For Sunday Jan 7 itself
    date_sun = whenever.Date(2024, 1, 7)
    weekly_open_sun = get_weekly_open_price_for_week(date_sun, sample_ohlc_df)
    print(f"Weekly Open Price relevant for {date_sun.format_common_iso()}: {weekly_open_sun}") # Expected: 100.00

    # Test missing data
    date_wed = whenever.Date(2024, 1, 10) # No data for this date in sample
    price_missing = get_midnight_open_price_for_day(date_wed, sample_ohlc_df)
    print(f"Midnight Open Price for {date_wed.format_common_iso()} (no data): {price_missing}") # Expected: None

# --- Time Window Check Functions ---

def is_within_time_window(
    dt_object: whenever.ZonedDateTime,
    start_time: whenever.Time,
    end_time: whenever.Time
) -> bool:
    """
    Checks if the time of a ZonedDateTime object falls within a given start and end time.
    The comparison is inclusive of the start_time and exclusive of the end_time.
    Assumes dt_object is already in the target timezone ('America/New_York').
    Handles overnight windows where end_time is earlier than start_time (e.g., 8 PM to 5 AM).
    """
    if dt_object.tz.name != TARGET_TZ_STR:
        # This check is a safeguard; calling code should ensure correct timezone.
        # Consider raising an error or logging a warning if this occurs.
        # For now, return False as it's an invalid state for these checks.
        print(f"Warning: is_within_time_window called with dt_object in incorrect timezone: {dt_object.tz.name}")
        return False

    current_obj_time = dt_object.time()

    if start_time <= end_time:
        # Standard window (e.g., 9:30 AM to 10:30 AM)
        return start_time <= current_obj_time < end_time
    else:
        # Overnight window (e.g., Asian session 8 PM to 10 PM, or a broader 8PM to 5AM next day)
        # True if current_time is after start_time (e.g., >= 8 PM)
        # OR current_time is before end_time (e.g., < 5 AM on the next day concept)
        # This logic is for checking if a time falls within a *defined daily repeating window*.
        # For Asian Killzone specifically, the "previous day" context is handled by the caller
        # or by how the specific `is_within_asian_killzone` is implemented if it needs to be smarter.
        # This helper is generic for time-only checks.
        return current_obj_time >= start_time or current_obj_time < end_time


def is_within_initial_balance_period(dt_object: whenever.ZonedDateTime) -> bool:
    """
    Checks if dt_object (in NY/ET) falls between 9:30 AM and 10:30 AM ET.
    (Inclusive of 9:30 AM, exclusive of 10:30 AM).
    """
    return is_within_time_window(dt_object, MARKET_OPEN_ET_TIME, IB_END_ET_TIME)

def is_within_ny_killzone(dt_object: whenever.ZonedDateTime) -> bool:
    """
    Checks if dt_object (in NY/ET) falls within the New York Killzone (7:00 AM – 9:00 AM ET).
    (Inclusive of 7:00 AM, exclusive of 9:00 AM).
    """
    return is_within_time_window(dt_object, NY_KILLZONE_START_TIME, NY_KILLZONE_END_TIME)

def is_within_london_killzone(dt_object: whenever.ZonedDateTime) -> bool:
    """
    Checks if dt_object (in NY/ET) falls within the London Killzone (2:00 AM – 5:00 AM ET).
    (Inclusive of 2:00 AM, exclusive of 5:00 AM).
    """
    return is_within_time_window(dt_object, LONDON_KILLZONE_START_TIME, LONDON_KILLZONE_END_TIME)

def is_within_london_close_killzone(dt_object: whenever.ZonedDateTime) -> bool:
    """
    Checks if dt_object (in NY/ET) falls within the London Close Killzone (10:00 AM – 12:00 PM ET).
    (Inclusive of 10:00 AM, exclusive of 12:00 PM).
    """
    return is_within_time_window(dt_object, LONDON_CLOSE_KILLZONE_START_TIME, LONDON_CLOSE_KILLZONE_END_TIME)

def is_within_asian_killzone(dt_object: whenever.ZonedDateTime) -> bool:
    """
    Checks if dt_object (in NY/ET) falls within the Asian Killzone (8:00 PM – 10:00 PM ET on its date).
    (Inclusive of 8:00 PM, exclusive of 10:00 PM).
    The "previous day" context for trading sessions is handled by the calling logic,
    this function checks the time on the given dt_object's date.
    """
    # Asian session is 8 PM to 10 PM. This is a standard window, not overnight for this specific 2-hour KZ.
    return is_within_time_window(dt_object, ASIAN_KILLZONE_START_TIME, ASIAN_KILLZONE_END_TIME)

def is_within_macro_time(
    dt_object: whenever.ZonedDateTime,
    macro_start_time: whenever.Time,
    macro_end_time: whenever.Time
) -> bool:
    """
    Generic function to check if dt_object (in NY/ET) falls within a custom macro time window.
    (Inclusive of macro_start_time, exclusive of macro_end_time).
    """
    return is_within_time_window(dt_object, macro_start_time, macro_end_time)

# --- Data-Dependent Price Retrieval Functions ---

def _get_price_at_time(
    target_dt: whenever.ZonedDateTime,
    ohlc_data_frame: pd.DataFrame
) -> float | None:
    """
    Helper function to retrieve the 'open' price for a specific target ZonedDateTime
    from an OHLC DataFrame.
    Assumes 'timestamp' column in ohlc_data_frame contains timezone-aware objects
    comparable to target_dt (ideally whenever.ZonedDateTime in NY_ZONEINFO).
    Assumes 'open' column contains the price.
    Assumes 1-minute granularity, so expects an exact match for the timestamp.
    """
    if not isinstance(target_dt, whenever.ZonedDateTime):
        print(f"Error (_get_price_at_time): target_dt must be a whenever.ZonedDateTime. Got: {type(target_dt)}")
        return None
    if 'timestamp' not in ohlc_data_frame.columns or 'open' not in ohlc_data_frame.columns:
        print("Error (_get_price_at_time): ohlc_data_frame must contain 'timestamp' and 'open' columns.")
        return None

    # Ensure target_dt is in NY_ZONEINFO for consistent comparison, though inputs should already be.
    # This is more of a defensive check if upstream data isn't perfectly clean.
    # However, the core assumption is that ohlc_data_frame['timestamp'] are ALREADY NY ZonedDateTimes.
    # Direct comparison should work if types are consistent.
    # If ohlc_data_frame['timestamp'] could be other types (e.g., pd.Timestamp),
    # conversion or more careful comparison might be needed.
    # For now, we assume direct equality check is sufficient given problem constraints.

    match = ohlc_data_frame[ohlc_data_frame['timestamp'] == target_dt]

    if not match.empty:
        if len(match) > 1:
            # This case should ideally not happen with 1-minute unique timestamp data.
            print(f"Warning (_get_price_at_time): Multiple records found for {target_dt}. Using the first one.")
        return match['open'].iloc[0]
    else:
        # print(f"Debug (_get_price_at_time): No record found for {target_dt}.")
        return None

def get_midnight_open_price_for_day(
    target_date: whenever.Date,
    ohlc_data_frame: pd.DataFrame
) -> float | None:
    """
    Retrieves the Open price of the candle that includes 12:00 AM NY time
    for the given target_date from ohlc_data_frame.
    """
    if not isinstance(target_date, whenever.Date):
        print("Error (get_midnight_open_price_for_day): target_date must be a whenever.Date.")
        return None

    # Create the ZonedDateTime for 12:00 AM on target_date in New York.
    # PlainDateTime.at() is combined with NY_ZONEINFO.convert() for DST handling.
    target_dt = NY_ZONEINFO.convert(target_date.at(MIDNIGHT_OPEN_ET_TIME), disambiguate='raise')
    return _get_price_at_time(target_dt, ohlc_data_frame)

def get_nyse_open_price_for_day(
    target_date: whenever.Date,
    ohlc_data_frame: pd.DataFrame
) -> float | None:
    """
    Retrieves the Open price of the 9:30 AM NY time candle for the given target_date.
    """
    if not isinstance(target_date, whenever.Date):
        print("Error (get_nyse_open_price_for_day): target_date must be a whenever.Date.")
        return None

    target_dt = NY_ZONEINFO.convert(target_date.at(MARKET_OPEN_ET_TIME), disambiguate='raise')
    return _get_price_at_time(target_dt, ohlc_data_frame)

def get_weekly_open_price_for_week(
    target_date: whenever.Date, # The day for which we want to find its relevant weekly open
    ohlc_data_frame: pd.DataFrame
) -> float | None:
    """
    Retrieves the Sunday 6:00 PM ET opening price for the week relevant to the target_date.
    For any day from Monday to Sunday, the relevant weekly open is the price at 6:00 PM ET
    on the most recent Sunday (or the current day if target_date is Sunday).
    """
    if not isinstance(target_date, whenever.Date):
        print("Error (get_weekly_open_price_for_week): target_date must be a whenever.Date.")
        return None

    # Find the date of the preceding Sunday (or current day if it's Sunday).
    # whenever.Weekday.SUNDAY has a value (e.g., 6 if Monday is 0).
    # previous_or_same() is the most direct way.
    sunday_date = target_date.previous_or_same(whenever.Weekday.SUNDAY)

    target_dt = NY_ZONEINFO.convert(sunday_date.at(WEEKLY_OPEN_SUNDAY_TIME), disambiguate='raise')
    return _get_price_at_time(target_dt, ohlc_data_frame)
