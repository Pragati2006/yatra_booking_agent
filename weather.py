"""
weather.py
Weather info for trip planning, shown alongside the hotel/taxi step
since that's where the darshan date is already fixed.

Two sources:
1. LIVE FORECAST - Open-Meteo (https://open-meteo.com), a free
   weather API that needs no API key. Only used for dates within its
   forecast window (roughly the next 16 days) since no forecast API
   is meaningfully accurate much further out than that.
2. SEASONAL AVERAGE - a small, real, researched table of Katra/Jammu
   monthly climate patterns, used as a fallback for dates beyond the
   forecast window, or if the live API call fails for any reason
   (no network, timeout, rate limit, etc). This always succeeds, so
   the app never breaks if this feature is used offline.

Coordinates used are for Katra town (the pilgrim base town), not the
Bhawan shrine itself (~5,200 ft up the trek route, which runs several
degrees cooler and can see winter snow even when Katra town doesn't -
this distinction is called out in the advisory text below).

Seasonal figures are grounded in real, well-documented climate
patterns for this part of the Trikuta Hills / Jammu region:
- Summers (Apr-Jun) are hot, peaking around 35°C in June before the
  monsoon breaks.
- The monsoon (Jul-Sep) brings heavy rain, with July typically the
  wettest month; the trek route can see slippery conditions and
  occasional landslide-related closures in this window.
- Autumn (Oct-Nov) is widely regarded as the most pleasant and driest
  window for the yatra.
- Winters (Dec-Feb) are cold and can be foggy; the Bhawan shrine
  (much higher altitude than Katra town) occasionally sees light snow.
This is general seasonal guidance, not a precise forecast - actual
conditions vary year to year.
"""

from datetime import date, datetime

import requests

KATRA_LAT = 33.03
KATRA_LON = 74.95

FORECAST_WINDOW_DAYS = 15  # Open-Meteo's daily forecast is reliable roughly this far out

SEASONAL_AVERAGES = {
    # month: (low_c, high_c, summary, advisory)
    1: (5, 15, "Cold, often foggy mornings", "Bhawan shrine (higher altitude) can see light snow; pack warm layers."),
    2: (7, 18, "Cold, clearing through the month", "Still cool at night; a jacket is worth packing."),
    3: (11, 23, "Mild and pleasant", "Good trekking weather, comfortable days."),
    4: (15, 28, "Warm, pleasant", "Good trekking weather before summer heat sets in."),
    5: (19, 32, "Hot", "Start early treks to avoid midday heat."),
    6: (22, 35, "Very hot, humid before monsoon", "Hottest month - carry extra water on the trek."),
    7: (22, 32, "Monsoon - heavy rain likely", "Trek route can be slippery; watch for landslide advisories."),
    8: (21, 31, "Monsoon - heavy rain likely", "Trek route can be slippery; watch for landslide advisories."),
    9: (19, 29, "Monsoon tapering off", "Rain becomes less frequent later in the month."),
    10: (13, 26, "Pleasant and dry", "Widely considered one of the best months for the yatra."),
    11: (8, 22, "Pleasant, cooling", "Dry and comfortable; nights turn cold."),
    12: (5, 16, "Cold", "Bhawan shrine (higher altitude) can see light snow; pack warm layers."),
}

WEATHER_CODE_SUMMARY = {
    0: "Clear sky", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Foggy",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Rain showers", 82: "Violent rain showers",
    95: "Thunderstorm",
}


def _seasonal_fallback(target_date):
    month = target_date.month
    low, high, summary, advisory = SEASONAL_AVERAGES[month]
    return {
        "source": "seasonal_average",
        "date": target_date.isoformat(),
        "summary": summary,
        "low_c": low,
        "high_c": high,
        "advisory": advisory,
    }


def _live_forecast(target_date):
    """Tries the Open-Meteo API for a real short-range forecast. Returns
    None (never raises) on any failure, so the caller can fall back."""
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": KATRA_LAT,
                "longitude": KATRA_LON,
                "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                "timezone": "auto",
                "start_date": target_date.isoformat(),
                "end_date": target_date.isoformat(),
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})
        if not daily.get("time"):
            return None
        code = daily["weathercode"][0]
        return {
            "source": "forecast",
            "date": target_date.isoformat(),
            "summary": WEATHER_CODE_SUMMARY.get(code, "Forecast available"),
            "low_c": round(daily["temperature_2m_min"][0]),
            "high_c": round(daily["temperature_2m_max"][0]),
            "advisory": "Live short-range forecast - conditions can still shift closer to the date.",
        }
    except Exception:
        return None


def get_weather(date_str):
    """Returns weather info for a given YYYY-MM-DD date: a live forecast
    if the date is near-term, otherwise a real seasonal average. Never
    raises - always returns a usable dict, even fully offline."""
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    days_out = (target_date - date.today()).days

    if 0 <= days_out <= FORECAST_WINDOW_DAYS:
        live = _live_forecast(target_date)
        if live:
            return live

    return _seasonal_fallback(target_date)


def get_weather_summary(location="Katra"):
    """Returns today's or default seasonal weather summary for Katra."""
    today_str = date.today().isoformat()
    return get_weather(today_str)

