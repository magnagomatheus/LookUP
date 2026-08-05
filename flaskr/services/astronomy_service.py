"""
astronomy_service.py
--------------------
Business / computation layer for the Celestial Observer app.

Responsibilities:
  - Geocoding (OpenCage API)
  - Sky / weather conditions (Open-Meteo API)
  - Planet visibility (ephem)
  - Lunar phase info (ephem)
  - Upcoming astronomical events (ephem)

No Flask request context is needed here — functions receive plain
values and return plain dicts / lists.
"""

import math
import os
from datetime import datetime

import ephem
import requests


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def get_coordinates(country: str, state: str, city: str):
    """
    Return (lat_str, lon_str) for the given location via OpenCage,
    or None if the lookup fails or no API key is set.
    """
    api_key = os.environ.get('OPENCAGE_API_KEY', '')
    if not api_key:
        return None

    url = 'https://api.opencagedata.com/geocode/v1/json'
    params = {
        'q': f'{city},{state},{country}',
        'key': api_key,
        'limit': 1,
        'no_annotations': 1,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        results = response.json().get('results', [])
        if results:
            geo = results[0]['geometry']
            return (str(geo['lat']), str(geo['lng']))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Sky / weather conditions
# ---------------------------------------------------------------------------

def get_sky_conditions(lat: str, lon: str) -> dict:
    """Return sky quality metrics from the Open-Meteo free API."""
    url = 'https://api.open-meteo.com/v1/forecast'
    params = {
        'latitude': lat,
        'longitude': lon,
        'current': [
            'temperature_2m',
            'cloud_cover',
            'visibility',
            'wind_speed_10m',
            'relative_humidity_2m',
            'weather_code',
        ],
        'timezone': 'auto',
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        current = response.json().get('current', {})

        cloud_cover = current.get('cloud_cover', 100)
        visibility  = current.get('visibility', 0)
        temp        = current.get('temperature_2m')
        humidity    = current.get('relative_humidity_2m')
        wind        = current.get('wind_speed_10m')
        wcode       = current.get('weather_code', 0)

        score = _observing_score(cloud_cover, visibility, humidity)
        rating, rating_class = _score_to_rating(score)

        return {
            'temperature':       temp,
            'cloud_cover':       cloud_cover,
            'visibility_km':     round(visibility / 1000, 1) if visibility else None,
            'humidity':          humidity,
            'wind_speed':        wind,
            'weather_description': _wmo_description(wcode),
            'observing_score':   score,
            'rating':            rating,
            'rating_class':      rating_class,
        }
    except Exception:
        return {
            'temperature': None, 'cloud_cover': None, 'visibility_km': None,
            'humidity': None, 'wind_speed': None,
            'weather_description': 'Unavailable',
            'observing_score': 0, 'rating': 'Unknown', 'rating_class': 'secondary',
        }


def _observing_score(cloud_cover: float, visibility_m: float, humidity) -> int:
    """Return an integer 0-100 representing sky quality for observation."""
    score = 100.0
    score -= cloud_cover * 0.7
    vis_km = (visibility_m or 0) / 1000
    if vis_km < 20:
        score -= (20 - vis_km) * 1.5
    if humidity and humidity > 60:
        score -= (humidity - 60) * 0.3
    return max(0, min(100, int(score)))


def _score_to_rating(score: int):
    if score >= 80:
        return ('Excellent', 'success')
    elif score >= 60:
        return ('Good', 'info')
    elif score >= 40:
        return ('Fair', 'warning')
    return ('Poor', 'danger')


def _wmo_description(code: int) -> str:
    descriptions = {
        0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
        45: 'Foggy', 48: 'Icy fog',
        51: 'Light drizzle', 53: 'Moderate drizzle', 55: 'Dense drizzle',
        61: 'Slight rain', 63: 'Moderate rain', 65: 'Heavy rain',
        71: 'Slight snow', 73: 'Moderate snow', 75: 'Heavy snow',
        80: 'Slight showers', 81: 'Moderate showers', 82: 'Violent showers',
        95: 'Thunderstorm', 96: 'Thunderstorm w/ hail', 99: 'Thunderstorm w/ heavy hail',
    }
    return descriptions.get(code, f'Code {code}')


# ---------------------------------------------------------------------------
# Planet visibility
# ---------------------------------------------------------------------------

_PLANETS = [
    ('Mercury', ephem.Mercury, '☿'),
    ('Venus',   ephem.Venus,   '♀'),
    ('Mars',    ephem.Mars,    '♂'),
    ('Jupiter', ephem.Jupiter, '♃'),
    ('Saturn',  ephem.Saturn,  '♄'),
    ('Uranus',  ephem.Uranus,  '⛢'),
    ('Neptune', ephem.Neptune, '♆'),
]


def get_planets_info(lat: str, lon: str) -> list:
    """Return a list of dicts with current visibility data for each planet."""
    observer = _make_observer(lat, lon)
    results = []

    for name, PlanetClass, symbol in _PLANETS:
        planet = PlanetClass()
        planet.compute(observer)

        alt_deg = math.degrees(float(planet.alt))
        az_deg  = math.degrees(float(planet.az))

        # Rise / set times
        try:
            obs_tmp = observer.copy()
            obs_tmp.horizon = '-0:34'
            rise_str = ephem.localtime(obs_tmp.next_rising(planet)).strftime('%H:%M')
            set_str  = ephem.localtime(obs_tmp.next_setting(planet)).strftime('%H:%M')
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            rise_str = set_str = '—'
        except Exception:
            rise_str = set_str = 'N/A'

        if alt_deg > 15:
            visibility, vis_class = 'Visible', 'success'
        elif alt_deg > 0:
            visibility, vis_class = 'Low on horizon', 'warning'
        else:
            visibility, vis_class = 'Below horizon', 'danger'

        try:
            constellation = ephem.constellation(planet)[1]
        except Exception:
            constellation = 'Unknown'

        results.append({
            'name':          name,
            'symbol':        symbol,
            'altitude':      round(alt_deg, 1),
            'azimuth':       round(az_deg, 1),
            'cardinal':      _degrees_to_cardinal(az_deg),
            'magnitude':     round(float(planet.mag), 1),
            'rise':          rise_str,
            'set':           set_str,
            'visibility':    visibility,
            'vis_class':     vis_class,
            'constellation': constellation,
        })

    order = {'Visible': 0, 'Low on horizon': 1, 'Below horizon': 2}
    results.sort(key=lambda p: (order[p['visibility']], -p['altitude']))
    return results


# ---------------------------------------------------------------------------
# Lunar phase
# ---------------------------------------------------------------------------

def get_lunar_info(lat: str, lon: str) -> dict:
    """Return current lunar phase and upcoming moon events."""
    observer = _make_observer(lat, lon)
    moon = ephem.Moon()
    moon.compute(observer)

    phase_pct = moon.phase
    alt_deg   = math.degrees(float(moon.alt))
    az_deg    = math.degrees(float(moon.az))

    try:
        obs_tmp  = observer.copy()
        rise_str = ephem.localtime(obs_tmp.next_rising(moon)).strftime('%H:%M')
        set_str  = ephem.localtime(obs_tmp.next_setting(moon)).strftime('%H:%M')
    except Exception:
        rise_str = set_str = 'N/A'

    if phase_pct > 75:
        moon_impact  = 'High — bright moon reduces visibility of faint objects'
        impact_class = 'danger'
    elif phase_pct > 40:
        moon_impact  = 'Moderate — best to observe after moonset'
        impact_class = 'warning'
    else:
        moon_impact  = 'Low — good conditions for deep-sky observation'
        impact_class = 'success'

    phase_name, phase_emoji = _moon_phase_name(phase_pct)
    now = observer.date

    return {
        'phase_pct':    round(phase_pct, 1),
        'phase_name':   phase_name,
        'phase_emoji':  phase_emoji,
        'altitude':     round(alt_deg, 1),
        'azimuth':      round(az_deg, 1),
        'cardinal':     _degrees_to_cardinal(az_deg),
        'rise':         rise_str,
        'set':          set_str,
        'next_new':     ephem.localtime(ephem.next_new_moon(now)).strftime('%b %d, %Y'),
        'next_full':    ephem.localtime(ephem.next_full_moon(now)).strftime('%b %d, %Y'),
        'next_first_q': ephem.localtime(ephem.next_first_quarter_moon(now)).strftime('%b %d, %Y'),
        'next_last_q':  ephem.localtime(ephem.next_last_quarter_moon(now)).strftime('%b %d, %Y'),
        'moon_impact':  moon_impact,
        'impact_class': impact_class,
    }


def _moon_phase_name(phase_pct: float):
    if phase_pct < 2:
        return ('New Moon', '🌑')
    elif phase_pct < 25:
        return ('Waxing Crescent', '🌒')
    elif phase_pct < 52:
        return ('First Quarter', '🌓')
    elif phase_pct < 75:
        return ('Waxing Gibbous', '🌔')
    elif phase_pct < 98:
        return ('Full Moon', '🌕')
    elif phase_pct < 100:
        return ('Waning Gibbous', '🌖')
    return ('New Moon', '🌑')


# ---------------------------------------------------------------------------
# Astronomical events
# ---------------------------------------------------------------------------

def get_astronomical_events(lat: str, lon: str) -> list:
    """Return a list of upcoming astronomical event dicts."""
    events = []
    now      = ephem.now()
    observer = _make_observer(lat, lon)

    # Solstices & Equinoxes
    _try_add(events, ephem.next_vernal_equinox,   now, 'Vernal Equinox',   '🌱', 'season',
             'Day and night are of equal length. Spring begins in the Northern Hemisphere.')
    _try_add(events, ephem.next_summer_solstice,  now, 'Summer Solstice',  '☀️', 'season',
             'Longest day of the year in the Northern Hemisphere.')
    _try_add(events, ephem.next_autumnal_equinox, now, 'Autumnal Equinox', '🍂', 'season',
             'Day and night are of equal length. Autumn begins in the Northern Hemisphere.')
    _try_add(events, ephem.next_winter_solstice,  now, 'Winter Solstice',  '❄️', 'season',
             'Shortest day of the year in the Northern Hemisphere.')

    # Moon phases
    _try_add(events, ephem.next_full_moon, now, 'Full Moon', '🌕', 'moon',
             'The Moon will be fully illuminated. Ideal for observing lunar surface details.',
             fmt='%b %d, %Y %H:%M')
    _try_add(events, ephem.next_new_moon,  now, 'New Moon',  '🌑', 'moon',
             'The Moon is not visible. Best night for deep-sky observation — darkest skies.',
             fmt='%b %d, %Y %H:%M')

    # Planetary oppositions / quadratures
    _add_planet_events(events, observer)

    events.sort(key=lambda e: e['date'])
    return events


def _try_add(events: list, ephem_fn, now, name: str, icon: str,
             event_type: str, desc: str, fmt: str = '%b %d, %Y') -> None:
    try:
        dt = ephem.localtime(ephem_fn(now)).strftime(fmt)
        events.append({'name': name, 'date': dt, 'desc': desc,
                       'icon': icon, 'type': event_type})
    except Exception:
        pass


def _add_planet_events(events: list, observer) -> None:
    sun = ephem.Sun()
    sun.compute(observer)
    sun_ra = float(sun.ra)

    outer_planets = [
        ('Mars',    ephem.Mars(),    '♂'),
        ('Jupiter', ephem.Jupiter(), '♃'),
        ('Saturn',  ephem.Saturn(),  '♄'),
    ]
    for name, planet, symbol in outer_planets:
        planet.compute(observer)
        sep = math.degrees(abs(float(planet.ra) - sun_ra))
        if sep > 180:
            sep = 360 - sep

        today = datetime.now().strftime('%b %d, %Y')
        if 160 <= sep <= 180:
            events.append({
                'name': f'{name} at Opposition',
                'date': today,
                'desc': f'{name} {symbol} is nearly opposite the Sun — closest approach, best visibility all night.',
                'icon': '🔭',
                'type': 'planet',
            })
        elif 80 <= sep <= 100:
            events.append({
                'name': f'{name} at Quadrature',
                'date': today,
                'desc': f'{name} {symbol} is 90° from the Sun — visible for half the night.',
                'icon': '🪐',
                'type': 'planet',
            })


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_observer(lat: str, lon: str) -> ephem.Observer:
    observer = ephem.Observer()
    observer.lat      = str(lat)
    observer.lon      = str(lon)
    observer.date     = ephem.now()
    observer.pressure = 0
    return observer


def _degrees_to_cardinal(deg: float) -> str:
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    return directions[int((deg + 22.5) / 45) % 8]
