from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
import requests

bp = Blueprint('core', __name__)


@bp.route('/', methods=('GET', 'POST'))
def index():

    #sending data
    if (request.method == "POST"):
        # efetuar html da localizacao
        country = request.form['country']
        state = request.form['state']
        city = request.form['city']

        error = None

        if not country:
            error = "You need to inform a country."
        elif not state:
            error = "You need to inform a state."
        elif not city:
            error = "You need to inform a city."
        
        if error is None:
            coordinates = get_coordinates(country, state, city)
        
        if not coordinates:
            return "It was not possible to get the coordinates of this location."
        
        lat, lon = coordinates

        weather_data = get_weather_data(lat, lon)
        return weather_data

        

        #return "Nothing"
    # first access
    else:
        return render_template("core/index.html")

def get_coordinates(country, state, city):

    headers = {
        'User-Agent': 'Lookup (someone@dominio.com)'
    }

    url = f"https://nominatim.openstreetmap.org/search?q={city},{state},{country}&format=json&limit=1"
    
    response = requests.get(url, headers=headers)

    data = response.json()

    if data:
        return (data[0]["lat"], data[0]["lon"])
    return None

def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["cloud_cover", "temperature_2m", "visibility"]
    }

    response = requests.get(url, params=params)

    data = response.json()
    return data