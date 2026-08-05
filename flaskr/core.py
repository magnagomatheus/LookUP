from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
import requests
import ephem
from datetime import datetime
import math
import os

from flaskr.auth import login_required

NO_DB = os.environ.get('NO_DB', 'false').lower() == 'true'

bp = Blueprint('core', __name__)


# ---------------------------------------------------------------------------
# Main index route
# ---------------------------------------------------------------------------

@bp.route('/', methods=('GET', 'POST'))
def index():
    saved_locations = []

    if g.user and not NO_DB:
        from flaskr.db import get_db
        db = get_db()
        saved_locations = db.execute(
            'SELECT * FROM SavedLocation WHERE fk_user = ? ORDER BY created_at DESC',
            (g.user['id'],)
        ).fetchall()

    if request.method == 'POST':
        country = request.form.get('country', '').strip()
        state   = request.form.get('state', '').strip()
        city    = request.form.get('city', '').strip()
        error   = None

        if not country:
            error = "You need to inform a country."
        elif not state:
            error = "You need to inform a state."
        elif not city:
            error = "You need to inform a city."

        if error:
            flash(error)
            return render_template('core/index.html', saved_locations=saved_locations)

        coordinates = get_coordinates(country, state, city)

        if not coordinates:
            flash("Could not find coordinates for this location. Please check the address.")
            return render_template('core/index.html', saved_locations=saved_locations)

        lat, lon = coordinates

        # Gather all data
        sky_conditions  = get_sky_conditions(lat, lon)
        planets         = get_planets_info(lat, lon)
        lunar           = get_lunar_info(lat, lon)
        events          = get_astronomical_events(lat, lon)

        location_label = f"{city}, {state}, {country}"

        return render_template(
            'core/results.html',
            location=location_label,
            lat=lat,
            lon=lon,
            country=country,
            state=state,
            city=city,
            sky=sky_conditions,
            planets=planets,
            lunar=lunar,
            events=events,
            now=datetime.now().strftime('%A, %B %d, %Y · %H:%M local'),
        )

    return render_template('core/index.html', saved_locations=saved_locations)


# ---------------------------------------------------------------------------
# Save address route (login required)
# ---------------------------------------------------------------------------

@bp.route('/save-address', methods=('POST',))
@login_required
def saveAddress():
    if NO_DB:
        flash('This feature is not available in this version.')
        return redirect(url_for('core.index'))

    from flaskr.db import get_db
    country = request.form.get('country', '').strip()
    state   = request.form.get('state', '').strip()
    city    = request.form.get('city', '').strip()
    lat     = request.form.get('lat', '').strip()
    lon     = request.form.get('lon', '').strip()
    label   = request.form.get('label', '').strip() or f"{city}, {state}"

    error = None
    if not country or not state or not city or not lat or not lon:
        error = "Missing location data to save."

    if error is None:
        db = get_db()
        # Avoid duplicates for the same user + city
        existing = db.execute(
            'SELECT id FROM SavedLocation WHERE fk_user = ? AND city = ? AND state = ? AND country = ?',
            (g.user['id'], city, state, country)
        ).fetchone()

        if existing:
            flash(f'Location "{label}" is already saved.')
        else:
            db.execute(
                'INSERT INTO SavedLocation (label, country, state, city, latitude, longitude, fk_user) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (label, country, state, city, lat, lon, g.user['id'])
            )
            db.commit()
            flash(f'Location "{label}" saved successfully!')
    else:
        flash(error)

    return redirect(url_for('core.index'))


# ---------------------------------------------------------------------------
# Delete saved address route (login required)
# ---------------------------------------------------------------------------

@bp.route('/delete-address/<int:loc_id>', methods=('POST',))
@login_required
def deleteAddress(loc_id):
    if NO_DB:
        flash('This feature is not available in this version.')
        return redirect(url_for('core.index'))

    from flaskr.db import get_db
    db = get_db()
    location = db.execute(
        'SELECT * FROM SavedLocation WHERE id = ? AND fk_user = ?',
        (loc_id, g.user['id'])
    ).fetchone()

    if location is None:
        flash("Location not found or access denied.")
    else:
        db.execute('DELETE FROM SavedLocation WHERE id = ?', (loc_id,))
        db.commit()
        flash(f'Location "{location["label"]}" removed.')

    return redirect(url_for('core.index'))


# ---------------------------------------------------------------------------
# Quick lookup for a saved location (loads results for that location)
# ---------------------------------------------------------------------------

@bp.route('/lookup/<int:loc_id>')
@login_required
def lookupSaved(loc_id):
    if NO_DB:
        flash('This feature is not available in this version.')
        return redirect(url_for('core.index'))

    from flaskr.db import get_db
    db = get_db()
    location = db.execute(
        'SELECT * FROM SavedLocation WHERE id = ? AND fk_user = ?',
        (loc_id, g.user['id'])
    ).fetchone()

    if location is None:
        flash("Location not found.")
        return redirect(url_for('core.index'))

    lat = str(location['latitude'])
    lon = str(location['longitude'])

    sky_conditions = get_sky_conditions(lat, lon)
    planets        = get_planets_info(lat, lon)
    lunar          = get_lunar_info(lat, lon)
    events         = get_astronomical_events(lat, lon)

    location_label = location['label']

    return render_template(
        'core/results.html',
        location=location_label,
        lat=lat,
        lon=lon,
        country=location['country'],
        state=location['state'],
        city=location['city'],
        sky=sky_conditions,
        planets=planets,
        lunar=lunar,
        events=events,
        now=datetime.now().strftime('%A, %B %d, %Y · %H:%M local'),
    )


# ---------------------------------------------------------------------------
# Helper: Geocoding via Nominatim (free, no key)
# ---------------------------------------------------------------------------

def get_coordinates(country, state, city):
    headers = {'User-Agent': 'CelestialObserver/1.0 (astronomical observation tool)'}
    url = (
        f"https://nominatim.openstreetmap.org/search"
        f"?q={city},{state},{country}&format=json&limit=1"
    )
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            return (data[0]['lat'], data[0]['lon'])
    except Exception as e:
        import sys
        print(f"[get_coordinates ERROR] {e}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Helper: Sky / weather conditions via open-meteo (free, no key)
# ---------------------------------------------------------------------------

def get_sky_conditions(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "cloud_cover",
            "visibility",
            "wind_speed_10m",
            "relative_humidity_2m",
            "weather_code",
        ],
        "timezone": "auto",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        current = data.get('current', {})

        cloud_cover = current.get('cloud_cover', 100)
        visibility  = current.get('visibility', 0)       # metres
        temp        = current.get('temperature_2m', None)
        humidity    = current.get('relative_humidity_2m', None)
        wind        = current.get('wind_speed_10m', None)
        wcode       = current.get('weather_code', 0)

        # Observing score 0-100
        score = _observing_score(cloud_cover, visibility, humidity)
        rating, rating_class = _score_to_rating(score)

        return {
            'temperature': temp,
            'cloud_cover': cloud_cover,
            'visibility_km': round(visibility / 1000, 1) if visibility else None,
            'humidity': humidity,
            'wind_speed': wind,
            'weather_description': _wmo_description(wcode),
            'observing_score': score,
            'rating': rating,
            'rating_class': rating_class,
        }
    except Exception:
        return {
            'temperature': None, 'cloud_cover': None, 'visibility_km': None,
            'humidity': None, 'wind_speed': None, 'weather_description': 'Unavailable',
            'observing_score': 0, 'rating': 'Unknown', 'rating_class': 'secondary',
        }


def _observing_score(cloud_cover, visibility_m, humidity):
    """Return an integer 0-100 representing sky quality for observation."""
    score = 100
    # Cloud penalty
    score -= cloud_cover * 0.7
    # Visibility penalty (ideal >= 20 km)
    vis_km = (visibility_m or 0) / 1000
    if vis_km < 20:
        score -= (20 - vis_km) * 1.5
    # Humidity penalty (ideal < 60%)
    if humidity and humidity > 60:
        score -= (humidity - 60) * 0.3
    return max(0, min(100, int(score)))


def _score_to_rating(score):
    if score >= 80:
        return ('Excellent', 'success')
    elif score >= 60:
        return ('Good', 'info')
    elif score >= 40:
        return ('Fair', 'warning')
    else:
        return ('Poor', 'danger')


def _wmo_description(code):
    """Map WMO weather interpretation code to a human-readable string."""
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
# Helper: Planet visibility using ephem (pure Python, no API)
# ---------------------------------------------------------------------------

PLANETS = [
    ('Mercury', ephem.Mercury, '☿'),
    ('Venus',   ephem.Venus,   '♀'),
    ('Mars',    ephem.Mars,    '♂'),
    ('Jupiter', ephem.Jupiter, '♃'),
    ('Saturn',  ephem.Saturn,  '♄'),
    ('Uranus',  ephem.Uranus,  '⛢'),
    ('Neptune', ephem.Neptune, '♆'),
]


def get_planets_info(lat, lon):
    observer = ephem.Observer()
    observer.lat  = str(lat)
    observer.lon  = str(lon)
    observer.date = ephem.now()
    observer.pressure = 0  # ignore atmospheric refraction for simplicity

    results = []
    for name, PlanetClass, symbol in PLANETS:
        planet = PlanetClass()
        planet.compute(observer)

        alt_deg  = math.degrees(float(planet.alt))
        az_deg   = math.degrees(float(planet.az))
        mag      = planet.mag

        # Rise / set times
        try:
            observer_tmp = observer.copy()
            observer_tmp.horizon = '-0:34'  # standard horizon dip
            rise_time = observer_tmp.next_rising(planet)
            set_time  = observer_tmp.next_setting(planet)
            rise_str  = ephem.localtime(rise_time).strftime('%H:%M')
            set_str   = ephem.localtime(set_time).strftime('%H:%M')
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            rise_str = set_str = '—'
        except Exception:
            rise_str = set_str = 'N/A'

        # Visibility status
        if alt_deg > 15:
            visibility = 'Visible'
            vis_class  = 'success'
        elif alt_deg > 0:
            visibility = 'Low on horizon'
            vis_class  = 'warning'
        else:
            visibility = 'Below horizon'
            vis_class  = 'danger'

        # Cardinal direction
        cardinal = _degrees_to_cardinal(az_deg)

        # Constellation
        try:
            constellation = ephem.constellation(planet)[1]
        except Exception:
            constellation = 'Unknown'

        results.append({
            'name':          name,
            'symbol':        symbol,
            'altitude':      round(alt_deg, 1),
            'azimuth':       round(az_deg, 1),
            'cardinal':      cardinal,
            'magnitude':     round(float(mag), 1),
            'rise':          rise_str,
            'set':           set_str,
            'visibility':    visibility,
            'vis_class':     vis_class,
            'constellation': constellation,
        })

    # Sort: visible first, then by altitude descending
    order = {'Visible': 0, 'Low on horizon': 1, 'Below horizon': 2}
    results.sort(key=lambda p: (order[p['visibility']], -p['altitude']))
    return results


def _degrees_to_cardinal(deg):
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    idx = int((deg + 22.5) / 45) % 8
    return directions[idx]


# ---------------------------------------------------------------------------
# Helper: Lunar phase using ephem
# ---------------------------------------------------------------------------

def get_lunar_info(lat, lon):
    observer = ephem.Observer()
    observer.lat  = str(lat)
    observer.lon  = str(lon)
    observer.date = ephem.now()

    moon = ephem.Moon()
    moon.compute(observer)

    phase_pct  = moon.phase          # 0-100
    alt_deg    = math.degrees(float(moon.alt))
    az_deg     = math.degrees(float(moon.az))
    cardinal   = _degrees_to_cardinal(az_deg)

    # Next phase events
    next_new      = ephem.localtime(ephem.next_new_moon(observer.date)).strftime('%b %d, %Y')
    next_full     = ephem.localtime(ephem.next_full_moon(observer.date)).strftime('%b %d, %Y')
    next_first_q  = ephem.localtime(ephem.next_first_quarter_moon(observer.date)).strftime('%b %d, %Y')
    next_last_q   = ephem.localtime(ephem.next_last_quarter_moon(observer.date)).strftime('%b %d, %Y')

    phase_name, phase_emoji = _moon_phase_name(phase_pct)

    # Rise / set
    try:
        observer_tmp = observer.copy()
        rise_str = ephem.localtime(observer_tmp.next_rising(moon)).strftime('%H:%M')
        set_str  = ephem.localtime(observer_tmp.next_setting(moon)).strftime('%H:%M')
    except Exception:
        rise_str = set_str = 'N/A'

    # Moon impact on observation
    if phase_pct > 75:
        moon_impact = 'High — bright moon reduces visibility of faint objects'
        impact_class = 'danger'
    elif phase_pct > 40:
        moon_impact = 'Moderate — best to observe after moonset'
        impact_class = 'warning'
    else:
        moon_impact = 'Low — good conditions for deep-sky observation'
        impact_class = 'success'

    return {
        'phase_pct':    round(phase_pct, 1),
        'phase_name':   phase_name,
        'phase_emoji':  phase_emoji,
        'altitude':     round(alt_deg, 1),
        'azimuth':      round(az_deg, 1),
        'cardinal':     cardinal,
        'rise':         rise_str,
        'set':          set_str,
        'next_new':     next_new,
        'next_full':    next_full,
        'next_first_q': next_first_q,
        'next_last_q':  next_last_q,
        'moon_impact':  moon_impact,
        'impact_class': impact_class,
    }


def _moon_phase_name(phase_pct):
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
    else:
        return ('New Moon', '🌑')


# ---------------------------------------------------------------------------
# Helper: Astronomical events (computed locally with ephem)
# ---------------------------------------------------------------------------

def get_astronomical_events(lat, lon):
    events = []
    now = ephem.now()

    observer = ephem.Observer()
    observer.lat  = str(lat)
    observer.lon  = str(lon)
    observer.date = now

    # --- Solstices & Equinoxes ---
    try:
        spring_eq = ephem.next_vernal_equinox(now)
        events.append({
            'name':  'Vernal Equinox',
            'date':  ephem.localtime(spring_eq).strftime('%b %d, %Y'),
            'desc':  'Day and night are of equal length. Spring begins in the Northern Hemisphere.',
            'icon':  '🌱',
            'type':  'season',
        })
    except Exception:
        pass

    try:
        summer_sol = ephem.next_summer_solstice(now)
        events.append({
            'name':  'Summer Solstice',
            'date':  ephem.localtime(summer_sol).strftime('%b %d, %Y'),
            'desc':  'Longest day of the year in the Northern Hemisphere.',
            'icon':  '☀️',
            'type':  'season',
        })
    except Exception:
        pass

    try:
        autumn_eq = ephem.next_autumnal_equinox(now)
        events.append({
            'name':  'Autumnal Equinox',
            'date':  ephem.localtime(autumn_eq).strftime('%b %d, %Y'),
            'desc':  'Day and night are of equal length. Autumn begins in the Northern Hemisphere.',
            'icon':  '🍂',
            'type':  'season',
        })
    except Exception:
        pass

    try:
        winter_sol = ephem.next_winter_solstice(now)
        events.append({
            'name':  'Winter Solstice',
            'date':  ephem.localtime(winter_sol).strftime('%b %d, %Y'),
            'desc':  'Shortest day of the year in the Northern Hemisphere.',
            'icon':  '❄️',
            'type':  'season',
        })
    except Exception:
        pass

    # --- Moon phases ---
    try:
        next_full = ephem.next_full_moon(now)
        events.append({
            'name':  'Full Moon',
            'date':  ephem.localtime(next_full).strftime('%b %d, %Y %H:%M'),
            'desc':  'The Moon will be fully illuminated. Ideal for observing lunar surface details.',
            'icon':  '🌕',
            'type':  'moon',
        })
    except Exception:
        pass

    try:
        next_new = ephem.next_new_moon(now)
        events.append({
            'name':  'New Moon',
            'date':  ephem.localtime(next_new).strftime('%b %d, %Y %H:%M'),
            'desc':  'The Moon is not visible. Best night for deep-sky observation — darkest skies.',
            'icon':  '🌑',
            'type':  'moon',
        })
    except Exception:
        pass

    # --- Planetary oppositions / conjunctions (Mars, Jupiter, Saturn) ---
    _add_planet_events(events, observer, now)

    # Sort events by date proximity
    events.sort(key=lambda e: e['date'])
    return events


def _add_planet_events(events, observer, now):
    """Detect upcoming planetary events: elongation peaks for inner planets,
    rough opposition hints for outer planets."""
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

        if 160 <= sep <= 180:
            events.append({
                'name':  f'{name} at Opposition',
                'date':  datetime.now().strftime('%b %d, %Y'),
                'desc':  f'{name} {symbol} is nearly opposite the Sun — closest approach, best visibility all night.',
                'icon':  '🔭',
                'type':  'planet',
            })
        elif 80 <= sep <= 100:
            events.append({
                'name':  f'{name} at Quadrature',
                'date':  datetime.now().strftime('%b %d, %Y'),
                'desc':  f'{name} {symbol} is 90° from the Sun — visible for half the night.',
                'icon':  '🪐',
                'type':  'planet',
            })
