import time
import datetime
from calendar import timegm

# Note: the 'Z' in the end of the ISO-8601 datetime string format means its in time zone 0, which means it's UTC0.
# However there are methods in this module that handle these strings as if they're in the user's localtime,
# which can be another timezone. Proper formatting dictates the timezone code in the string should change (when
# creating date-str) and that we should process this code to know when to use localtime or not.
iso_format = "%Y-%m-%dT%H:%M:%SZ"


sleep = time.sleep
timezone = time.timezone


def get_info_from_date(date_str):
    """Converts the given ISO datetime string into a Python's struct_time object.
    The object's value is in the same timezone as the date-str. However, for now at least,
    the time object returned here has no data to indicate this."""
    return time.strptime(date_str, iso_format)


def get_epoch_time_from_date(date_str, localtime=True):
    """Converts the ISO-8601 datetime string DATE_STR to a epoch-time integer.
    If LOCALTIME is true, DATE_STR is assumed to be in localtime, and the returned value will
    reflect that. Otherwise it's assumed to be in UTC0."""
    epoch = timegm(time.strptime(date_str, iso_format))
    if localtime:
        return epoch + time.timezone
    return epoch


def get_date_from_epoch_time(epoch, localtime=True):
    """Converts the given EPOCH-time integer to the ISO-8601 string representation.
    If LOCALTIME is true, the string is in localtime, otherwise it's in UTC0 time."""
    if localtime:
        return time.strftime(iso_format, time.localtime(epoch))
    return time.strftime(iso_format, time.gmtime(epoch))


def get_current_epoch(localtime=False):
    """Gets the current time, as a UTC0 epoch value.
    If LOCALTIME is true, returned value is in the local timezone instead."""
    if localtime:
        return time.time() + time.timezone
    return time.time()


def get_current_date(localtime=True):
    """Gets the current date in an ISO-8601 string format.
    If LOCALTIME is true, the date returned is in localtime, otherwise it is in UTC0."""
    return get_date_from_epoch_time(get_current_epoch(), localtime=localtime)


def clamp_hour(hour):
    """Clamps the given value to the hour value range: (0-23)

    This changes the given value to actual hour in the day. Examples:
    * 1 --> 1
    * 20 --> 20
    * -3 --> 21
    * -11 --> 13
    * 28 --> 4
    * 24 --> 0
    * 48 --> 0
    """
    return hour % 24


def get_delta_between(timestamp_a, timestamp_b=None, include_micro=False, localtime=False):
    """Gets the timedelta between the given TIMESTAMPs A and B. Essentially Delta = A - B.

    Each TIMESTAMP may be a numeric epoch value, or a ISO date string. In the latter case, the string
    is converted to a epoch value using `get_epoch_time_from_date`, and thus may use the LOCALTIME flag.

    TIMESTAMP_B may be None. In this case, we'll use the current epoch in its place (from `get_current_epoch` with the
    given LOCALTIME flag).

    If INCLUDE_MICRO is true, the time delta may include microseconds info, if available from the timestamps diff."""
    if isinstance(timestamp_a, str):
        timestamp_a = get_epoch_time_from_date(timestamp_a, localtime=localtime)
    if isinstance(timestamp_b, str):
        timestamp_b = get_epoch_time_from_date(timestamp_b, localtime=localtime)
    elif timestamp_b is None:
        timestamp_b = get_current_epoch(localtime=localtime)
    seconds = timestamp_a - timestamp_b
    delta = datetime.timedelta(seconds=seconds)
    if not include_micro:
        delta -= datetime.timedelta(microseconds=delta.microseconds)
    return delta


def get_datetime_from_iso(date_str, localtime=False):
    """Converts the given ISO-8601 DATE_STRing into a Python's datetime object.
    This assumes the DATE_STR represent a time related to the UTC0 timezone.

    If LOCALTIME is true, the DATE_STR is then assumed to be in the local timezone, and the returned datetime will reflect that.
    """
    dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    if localtime:
        dt = dt.astimezone()
    return dt
