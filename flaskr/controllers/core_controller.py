"""
core_controller.py
------------------
Controller (View layer in Flask terms) for the main application routes.

Responsibilities:
  - Handle HTTP request/response cycle for /, /save-address, /delete-address, /lookup
  - Delegate astronomical computations to AstronomyService
  - Delegate database operations to SavedLocationModel
  - Render templates or redirect as appropriate
"""

import os
from datetime import datetime

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)

from flaskr.controllers.auth_controller import login_required
from flaskr.models.saved_location import SavedLocationModel
from flaskr.services.astronomy_service import (
    get_coordinates,
    get_sky_conditions,
    get_planets_info,
    get_lunar_info,
    get_astronomical_events,
)

bp = Blueprint('core', __name__)

NO_DB = os.environ.get('NO_DB', 'false').lower() == 'true'


# ---------------------------------------------------------------------------
# Main index route
# ---------------------------------------------------------------------------

@bp.route('/', methods=('GET', 'POST'))
def index():
    saved_locations = []

    if g.user and not NO_DB:
        saved_locations = SavedLocationModel.get_all_by_user(g.user['id'])

    if request.method == 'POST':
        country = request.form.get('country', '').strip()
        state   = request.form.get('state', '').strip()
        city    = request.form.get('city', '').strip()
        error   = None

        if not country:
            error = 'You need to inform a country.'
        elif not state:
            error = 'You need to inform a state.'
        elif not city:
            error = 'You need to inform a city.'

        if error:
            flash(error)
            return render_template('core/index.html', saved_locations=saved_locations)

        coordinates = get_coordinates(country, state, city)
        if not coordinates:
            flash('Could not find coordinates for this location. Please check the address.')
            return render_template('core/index.html', saved_locations=saved_locations)

        lat, lon = coordinates
        return _render_results(lat, lon, country, state, city)

    return render_template('core/index.html', saved_locations=saved_locations)


# ---------------------------------------------------------------------------
# Save address route
# ---------------------------------------------------------------------------

@bp.route('/save-address', methods=('POST',))
@login_required
def saveAddress():
    if NO_DB:
        flash('This feature is not available in this version.')
        return redirect(url_for('core.index'))

    country = request.form.get('country', '').strip()
    state   = request.form.get('state', '').strip()
    city    = request.form.get('city', '').strip()
    lat     = request.form.get('lat', '').strip()
    lon     = request.form.get('lon', '').strip()
    label   = request.form.get('label', '').strip() or f'{city}, {state}'

    if not all([country, state, city, lat, lon]):
        flash('Missing location data to save.')
        return redirect(url_for('core.index'))

    if SavedLocationModel.exists(g.user['id'], city, state, country):
        flash(f'Location "{label}" is already saved.')
    else:
        SavedLocationModel.create(label, country, state, city, lat, lon, g.user['id'])
        flash(f'Location "{label}" saved successfully!')

    return redirect(url_for('core.index'))


# ---------------------------------------------------------------------------
# Delete saved address route
# ---------------------------------------------------------------------------

@bp.route('/delete-address/<int:loc_id>', methods=('POST',))
@login_required
def deleteAddress(loc_id):
    if NO_DB:
        flash('This feature is not available in this version.')
        return redirect(url_for('core.index'))

    location = SavedLocationModel.get_by_id_and_user(loc_id, g.user['id'])

    if location is None:
        flash('Location not found or access denied.')
    else:
        SavedLocationModel.delete(loc_id)
        flash(f'Location "{location["label"]}" removed.')

    return redirect(url_for('core.index'))


# ---------------------------------------------------------------------------
# Quick lookup for a saved location
# ---------------------------------------------------------------------------

@bp.route('/lookup/<int:loc_id>')
@login_required
def lookupSaved(loc_id):
    if NO_DB:
        flash('This feature is not available in this version.')
        return redirect(url_for('core.index'))

    location = SavedLocationModel.get_by_id_and_user(loc_id, g.user['id'])

    if location is None:
        flash('Location not found.')
        return redirect(url_for('core.index'))

    lat = str(location['latitude'])
    lon = str(location['longitude'])
    return _render_results(
        lat, lon,
        location['country'], location['state'], location['city'],
        label=location['label'],
    )


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------

def _render_results(lat: str, lon: str, country: str, state: str, city: str,
                    label: str = None):
    """Gather all astronomical data and render the results template."""
    location_label = label or f'{city}, {state}, {country}'

    return render_template(
        'core/results.html',
        location=location_label,
        lat=lat,
        lon=lon,
        country=country,
        state=state,
        city=city,
        sky=get_sky_conditions(lat, lon),
        planets=get_planets_info(lat, lon),
        lunar=get_lunar_info(lat, lon),
        events=get_astronomical_events(lat, lon),
        now=datetime.now().strftime('%A, %B %d, %Y · %H:%M local'),
    )
