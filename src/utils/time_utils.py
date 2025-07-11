import whenever
import pandas as pd # Keep for initial flexible string parsing
from datetime import datetime as std_datetime, date as std_date, timezone as std_timezone # For type hints and conversion from pandas

# Define the target timezone string
TARGET_TZ = "America/New_York"

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
            return timestamp_input.to_tz(TARGET_TZ)
        if isinstance(timestamp_input, whenever.ZonedDateTime):
            if timestamp_input.tz == TARGET_TZ:
                return timestamp_input
            return timestamp_input.to_tz(TARGET_TZ)
        if isinstance(timestamp_input, whenever.PlainDateTime):
            if not original_tz_str:
                print(f"Error: whenever.PlainDateTime provided without original_tz_str. Ambiguous conversion for {timestamp_input}.")
                return None
            # This will raise SkippedTime or RepeatedTime if ambiguous and disambiguate='raise' (default for assume_tz)
            # For our purpose, we want to know if the original_tz makes it invalid, so 'raise' is good.
            return timestamp_input.assume_tz(original_tz_str, disambiguate='raise').to_tz(TARGET_TZ)

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
                return plain_dt.assume_tz(original_tz_str, disambiguate='raise').to_tz(TARGET_TZ)
            else: # Aware Python datetime
                # Convert aware Python datetime to whenever.Instant first, then to ZonedDateTime
                # Note: whenever.Instant.from_py_datetime expects UTC or raises error if tz is not ZoneInfo UTC.
                # A more general path for aware py_dt is to convert to its UTC equivalent instant.
                # If it has ZoneInfo, ZonedDateTime.from_py_datetime(py_dt).to_tz(TARGET_TZ) is better.
                if isinstance(py_dt.tzinfo, type(std_timezone.utc)): # Check if it's stdlib UTC
                     instant = whenever.Instant.from_py_datetime(py_dt)
                     return instant.to_tz(TARGET_TZ)
                try:
                    # Attempt to convert directly if tzinfo is ZoneInfo (used by whenever)
                    # This requires py_dt.tzinfo to be a zoneinfo.ZoneInfo object.
                    # If pandas parsed a string with tz, it might be zoneinfo.
                    zdt = whenever.ZonedDateTime.from_py_datetime(py_dt)
                    return zdt.to_tz(TARGET_TZ)
                except ValueError: # Likely if tzinfo is not what whenever expects (e.g. pytz)
                    # Fallback: convert to UTC instant then to target TZ
                    utc_py_dt = py_dt.astimezone(std_timezone.utc)
                    instant = whenever.Instant.from_py_datetime(utc_py_dt)
                    return instant.to_tz(TARGET_TZ)


        # 3. Handle Unix timestamp (int/float)
        if isinstance(timestamp_input, (int, float)):
            return whenever.Instant.from_timestamp(int(timestamp_input)).to_tz(TARGET_TZ)

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
                        return odt.to_tz(TARGET_TZ)
                    except ValueError: # If not OffsetDateTime ISO, try Instant ISO (for Z)
                        instant = whenever.Instant.parse_common_iso(s)
                        return instant.to_tz(TARGET_TZ)
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
                    # If still naive and no TZ info from string or args, assume TARGET_TZ
                    final_original_tz_for_conversion = TARGET_TZ

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
    open_time_str: str = "09:30",
    close_time_str: str = "16:00"
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

        open_hour, open_minute = map(int, open_time_str.split(':'))
        close_hour, close_minute = map(int, close_time_str.split(':'))

        if not (0 <= open_hour <= 23 and 0 <= open_minute <= 59 and \
                0 <= close_hour <= 23 and 0 <= close_minute <= 59):
            raise ValueError("Hour or minute out of valid range.")

        # Construct ZonedDateTime directly.
        # For typical market hours (9:30, 16:00), 'compatible' or 'raise' are usually fine.
        # 'raise' is safer to ensure the exact time is valid.
        # 'compatible' mimics Python's datetime.astimezone behavior during DST transitions.
        # Let's use 'raise' to be strict.
        market_open_et = whenever.ZonedDateTime(
            w_date.year, w_date.month, w_date.day,
            open_hour, open_minute,
            tz=TARGET_TZ,
            disambiguate='raise'
        )
        market_close_et = whenever.ZonedDateTime(
            w_date.year, w_date.month, w_date.day,
            close_hour, close_minute,
            tz=TARGET_TZ,
            disambiguate='raise'
        )
        return market_open_et, market_close_et

    except (ValueError, TypeError) as e_parse: # Catches map/split errors, int conversion, out of range
        print(f"Error parsing time strings or date: '{open_time_str}', '{close_time_str}'. {e_parse}")
        return None, None
    except (whenever.SkippedTime, whenever.RepeatedTime) as e_dst:
        # This would be rare for 9:30/16:00 but good to catch.
        print(f"Error: DST transition issue for market time on {w_date.format_common_iso()}: {e_dst}")
        return None, None
    except whenever.TimeZoneNotFoundError as e_tz_not_found:
        print(f"Error: Timezone '{TARGET_TZ}' not found: {e_tz_not_found}")
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
