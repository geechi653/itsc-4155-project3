from flask import Flask, render_template, request, jsonify, url_for
import requests
from datetime import datetime
from functools import wraps
from time import time
from collections import defaultdict
from flask import session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'ee7ea1ebacf0f523ae4b3c285a59b34e'


def init_db():
    conn = sqlite3.connect('weather_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS search_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  city TEXT NOT NULL,
                  search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()


def alter_db():
    conn = sqlite3.connect('weather_history.db')
    c = conn.cursor()
    try:
        c.execute('ALTER TABLE search_history MODIFY COLUMN city TEXT(255)')
    except:
        pass  # SQLite doesn't support ALTER COLUMN, but TEXT should already handle long strings
    conn.close()


init_db()


def save_search(city):
    conn = sqlite3.connect('weather_history.db')
    c = conn.cursor()
    c.execute('INSERT INTO search_history (city) VALUES (?)', (city,))
    conn.commit()
    conn.close()

def get_search_history():
    conn = sqlite3.connect('weather_history.db')
    c = conn.cursor()
    c.execute('SELECT DISTINCT city, MAX(search_date) FROM search_history GROUP BY city ORDER BY search_date DESC LIMIT 5')
    history = c.fetchall()
    conn.close()
    return history

# OpenWeatherMap API key
API_KEY = '983e0f4c72e18f96cfe6e16ac315c528'

def get_weather_tip(weather_desc, temp, humidity, wind_speed, unit='imperial'):
    """Generate weather tips based on conditions."""
    tips = []
    
    # Temperature-based tips
    if unit == 'imperial':
        if temp > 75:
            tips.append("🌡️ Warm temperature! Stay hydrated and consider sunscreen.")
        elif temp > 60:
            tips.append("💡 Perfect weather for outdoor activities! Consider sunscreen.")
        elif temp > 40:
            tips.append("💡 Good weather for outdoor activities! Dress in layers.")
        elif temp > 32:
            tips.append("🧥 Cool conditions - dress warmly for outdoor activities.")
        else:
            tips.append("❄️ Freezing conditions! Bundle up and watch for ice.")
    else:
        if temp > 23:
            tips.append("🌡️ Warm temperature! Stay hydrated and consider sunscreen.")
        elif temp > 15:
            tips.append("💡 Perfect weather for outdoor activities! Consider sunscreen.")
        elif temp > 4:
            tips.append("💡 Good weather for outdoor activities! Dress in layers.")
        elif temp > 0:
            tips.append("🧥 Cool conditions - dress warmly for outdoor activities.")
        else:
            tips.append("❄️ Freezing conditions! Bundle up and watch for ice.")

    # Wind-based tips
    if wind_speed > 10:
        tips.append("💨 Strong winds! Secure loose objects and be careful when driving.")
    
    # Weather condition-based tips
    weather_desc = weather_desc.lower()
    if "clear" in weather_desc:
        if (unit == 'imperial' and temp > 60) or (unit == 'metric' and temp > 15):
            tips.append("☀️ Clear skies! Don't forget sunscreen.")
        else:
            tips.append("☀️ Clear skies! Great visibility for outdoor activities.")
    elif "few clouds" in weather_desc or "scattered clouds" in weather_desc:
        tips.append("💡 Good conditions for outdoor activities with partial cloud cover.")
    elif "broken clouds" in weather_desc or "overcast" in weather_desc:
        tips.append("💡 Cloudy conditions - good for outdoor activities but keep an eye on changes.")
    elif "rain" in weather_desc or "drizzle" in weather_desc:
        tips.append("☔ Rainy conditions - bring an umbrella and wear waterproof clothing.")
    elif "thunderstorm" in weather_desc:
        tips.append("⚡ Thunderstorm warning! Stay indoors and avoid open areas.")
    elif "snow" in weather_desc:
        tips.append("🌨️ Snowy conditions - dress warmly and be careful on roads.")
    elif "mist" in weather_desc or "fog" in weather_desc:
        tips.append("🌫️ Reduced visibility - use caution while driving.")

    # Humidity-based tips
    if humidity > 70:
        tips.append("💧 High humidity - it may feel warmer than the actual temperature.")
    elif humidity < 30:
        tips.append("🏜️ Low humidity - remember to stay hydrated.")

    return tips

# Rate limiting decorator
def rate_limit(limit=60, per=60):
    rates = defaultdict(lambda: [0, time()])
    
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            now = time()
            rates[f.__name__][0] += 1
            
            if now - rates[f.__name__][1] > per:
                rates[f.__name__] = [1, now]
            elif rates[f.__name__][0] > limit:
                return jsonify({'error': 'Rate limit exceeded'}), 429
                
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.route('/')
def home():
    unit = request.args.get('unit', 'imperial')
    return render_template('home.html', unit=unit)

@app.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method == 'POST':
        return render_template('home.html')
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        return render_template('home.html')
    return render_template('login.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        if 'lat' in request.form and 'lon' in request.form:
            lat = request.form['lat']
            lon = request.form['lon']
            city = request.form['city_name']
            state = request.form.get('state', '')
            country = request.form.get('country', '')
            
            formatted_city = format_city_name(city, state, country)
            
            unit = request.form.get('unit', 'imperial')
            weather_data = get_weather_by_coords(lat, lon, unit)
            
            if weather_data is not None:
                save_search(formatted_city)
                history = get_search_history()
                return render_template('search.html', weather=weather_data, city=formatted_city, unit=unit, history=history)
        else:
            city = request.form['city']
            unit = request.form.get('unit', 'imperial')
            cities = get_cities(city)
            
            if not cities:
                history = get_search_history()
                return render_template('search.html', error="City not found.", unit=unit, history=history)
            
            if len(cities) > 1:
                return render_template('city_select.html', 
                                    cities=cities, 
                                    unit=unit,
                                    redirect_url=url_for('search'))
            
            weather_data = get_weather(city, unit)

        if weather_data is not None:
            save_search(city)
            history = get_search_history()
            return render_template('search.html', weather=weather_data, city=city, unit=unit, history=history)
        else:
            history = get_search_history()
            return render_template('search.html', error="Weather data not available.", unit=unit, history=history)

    history = get_search_history()
    return render_template('search.html', unit=request.args.get('unit', 'imperial'), history=history)

@app.route('/forecast', methods=['GET', 'POST'])
def forecast():
    if request.method == 'POST':
        if 'lat' in request.form and 'lon' in request.form:
            lat = request.form['lat']
            lon = request.form['lon']
            city = request.form['city_name']
            state = request.form.get('state', '')
            country = request.form.get('country', '')
            
            formatted_city = format_city_name(city, state, country)
            
            unit = request.form.get('unit', 'imperial')
            forecast_data = get_five_day_forecast_by_coords(lat, lon, unit)
            
            if forecast_data is not None:
                return render_template('forecast.html', forecast=forecast_data, city=formatted_city, unit=unit)
        else:
            city = request.form['city']
            unit = request.form.get('unit', 'imperial')
            cities = get_cities(city)
            
            if not cities:
                return render_template('forecast.html', error="City not found.", unit=unit)
            
            if len(cities) > 1:
                return render_template('city_select.html', 
                                    cities=cities, 
                                    unit=unit,
                                    redirect_url=url_for('forecast'))
            
            forecast_data = get_five_day_forecast(city, unit)

        if forecast_data is not None:
            return render_template('forecast.html', forecast=forecast_data, city=city, unit=unit)
        else:
            return render_template('forecast.html', error="Forecast data not available.", unit=unit)

    return render_template('forecast.html', unit=request.args.get('unit', 'imperial'))

@app.route('/map')
def map():
    unit = request.args.get('unit', 'imperial')
    return render_template('map.html', unit=unit)

@app.route('/get_temperature_data')
@rate_limit()
def get_temperature_data():
    lat = request.args.get('lat', 0)
    lon = request.args.get('lon', 0)
    unit = request.args.get('unit', 'imperial')
    
    try:
        weather_data = get_weather_by_coords(lat, lon, unit)
        if not weather_data:
            return jsonify({'error': 'Could not fetch weather data'}), 500

        # Get location name using reverse geocoding
        geocode_url = f'http://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=1&appid={API_KEY}'
        geocode_response = requests.get(geocode_url)
        geocode_response.raise_for_status()
        location_data = geocode_response.json()
        location_name = location_data[0]['name'] if location_data else "Unknown Location"
        
        return jsonify({
            'temperature': weather_data['temperature'],
            'feels_like': weather_data.get('temp_min', weather_data['temperature']),
            'humidity': weather_data['humidity'],
            'wind': weather_data['wind'],
            'unit': weather_data['unit'],
            'description': weather_data['weather_desc'],
            'icon': weather_data['icon'],  
            'icon_class': weather_data['icon_class'],
            'location_name': location_name
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_aqi(lat, lon):
    """Fetch AQI data using latitude and longitude."""
    url = f'http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        aqi_level = data['list'][0]['main']['aqi']
        aqi_info = {
            1: {'level': 'Good', 'class': 'aqi-good'},
            2: {'level': 'Fair', 'class': 'aqi-fair'},
            3: {'level': 'Moderate', 'class': 'aqi-moderate'},
            4: {'level': 'Poor', 'class': 'aqi-poor'},
            5: {'level': 'Very Poor', 'class': 'aqi-very-poor'}
        }
        
        return aqi_info.get(aqi_level, {'level': 'Unavailable', 'class': 'aqi-unavailable'})
    except Exception as e:
        print(f"Error fetching AQI data: {e}")
        return {'level': 'Unavailable', 'class': 'aqi-unavailable'}    

def get_weather(city, unit='imperial'):
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units={unit}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()    
        if data.get('cod') != 200:
            return None
        lat = data['coord']['lat']
        lon = data['coord']['lon']
        aqi_data = get_aqi(lat, lon)
        
        icon_code = data['weather'][0]['icon']
        weather_info = {
            'temperature': data['main']['temp'],
            'temp_min': data['main']['temp_min'],
            'temp_max': data['main']['temp_max'],
            'humidity': data['main']['humidity'],
            'weather_desc': data['weather'][0]['description'],
            'wind': data['wind'],
            'icon': icon_code,
            'icon_class': get_weather_icon_class(icon_code),
            'unit': '°F' if unit == 'imperial' else '°C',
            'aqi': aqi_data,
            'tips': get_weather_tip(data['weather'][0]['description'], data['main']['temp'], data['main']['humidity'], data['wind']['speed'], unit),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')  
        }
        return weather_info
    except Exception as e:
        print(f"Error in get_weather: {e}")
        return None

def get_five_day_forecast(city, unit='imperial'):
    """Get 5-day weather forecast data using city name."""
    url = f'http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units={unit}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get('cod') != '200':
            return None
        forecast = process_five_day_forecast(data, unit)
        return forecast
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
    return None
def process_five_day_forecast(data, unit='imperial'):
    """Process the 5-day forecast data."""
    forecast_summary = []
    daily_data = defaultdict(list)
    
    for item in data['list']:
        date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
        daily_data[date].append(item)
    
    for date, items in daily_data.items():
        if len(forecast_summary) >= 6:  # Limit to 6 days
            break
            
        temps = [item['main']['temp'] for item in items]
        humidity = [item['main']['humidity'] for item in items]
        wind_speeds = [item['wind']['speed'] for item in items]
        
        
        weather_priority = {
            'thunderstorm': 5,
            'rain': 4,
            'snow': 4,
            'drizzle': 3,
            'clouds': 2,
            'clear': 1
        }
        
        
        max_priority = -1
        common_description = None
        common_icon = None
        
        for item in items:
            weather = item['weather'][0]
            main_weather = weather['main'].lower()
            for condition, priority in weather_priority.items():
                if condition in main_weather and priority > max_priority:
                    max_priority = priority
                    common_description = weather['description']
                    common_icon = weather['icon']
        
       
        if common_description is None:
            weather_conditions = [item['weather'][0]['description'] for item in items]
            weather_icons = [item['weather'][0]['icon'] for item in items]
            common_description = max(set(weather_conditions), key=weather_conditions.count)
            common_icon = max(set(weather_icons), key=weather_icons.count)
        
        avg_temp = sum(temps) / len(temps)
        avg_humidity = sum(humidity) / len(humidity)
        avg_wind_speed = sum(wind_speeds) / len(wind_speeds)
        
        dt = datetime.strptime(date, '%Y-%m-%d')
        
        lat = data['city']['coord']['lat']
        lon = data['city']['coord']['lon']
        aqi_data = get_aqi(lat, lon)
        
        
        tips = get_weather_tip(
            common_description,
            avg_temp,
            avg_humidity,
            avg_wind_speed,
            unit
        )
        
        forecast_summary.append({
            'date': dt.strftime('%Y-%m-%d'),
            'day_of_week': dt.strftime('%A'),
            'avg_temp': avg_temp,
            'avg_humidity': avg_humidity,
            'avg_wind_speed': avg_wind_speed,
            'description': common_description.title(),  
            'icon': common_icon,
            'icon_class': get_weather_icon_class(common_icon),
            'aqi': aqi_data,
            'unit': '°F' if unit == 'imperial' else '°C',
            'tips': tips,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return forecast_summary

            ##     old code, may be useful later    ##
# def process_five_day_forecast(data, unit='imperial'):
#     """Process the 5-day forecast data."""
#     forecast_summary = []
#     daily_data = defaultdict(list)
    
#     for item in data['list']:
#         date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
#         daily_data[date].append(item)
    
#     for date, items in daily_data.items():
#         if len(forecast_summary) >= 6:  # Limit to 6 days
#             break
            
#         temps = [item['main']['temp'] for item in items]
#         humidity = [item['main']['humidity'] for item in items]
#         wind_speeds = [item['wind']['speed'] for item in items]
        
#         # Get the most common weather condition for the day
#         weather_conditions = [item['weather'][0]['description'] for item in items]
#         weather_icons = [item['weather'][0]['icon'] for item in items]
#         common_description = max(set(weather_conditions), key=weather_conditions.count)
#         common_icon = max(set(weather_icons), key=weather_icons.count)
        
#         avg_temp = sum(temps) / len(temps)
#         avg_humidity = sum(humidity) / len(humidity)
#         avg_wind_speed = sum(wind_speeds) / len(wind_speeds)
        
#         dt = datetime.strptime(date, '%Y-%m-%d')
        
#         lat = data['city']['coord']['lat']
#         lon = data['city']['coord']['lon']
#         aqi_data = get_aqi(lat, lon)
        
#         forecast_summary.append({
#             'date': dt.strftime('%Y-%m-%d'),
#             'day_of_week': dt.strftime('%A'),
#             'avg_temp': avg_temp,
#             'avg_humidity': avg_humidity,
#             'avg_wind_speed': avg_wind_speed,
#             'description': common_description,
#             'icon': common_icon,
#             'icon_class': get_weather_icon_class(common_icon),  
#             'aqi': aqi_data,
#             'unit': '°F' if unit == 'imperial' else '°C',
#             'tips': get_weather_tip(common_description, avg_temp, avg_humidity, avg_wind_speed, unit),
#             'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#         })
    
#     return forecast_summary

def get_cities(city_name):
    """Get list of cities matching the name."""
    url = f'http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=5&appid={API_KEY}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching cities: {e}")
        return None

def get_weather_by_coords(lat, lon, unit='imperial'):
    """Get weather using coordinates."""
    url = f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units={unit}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get('cod') != 200:
            return None
            
        aqi_data = get_aqi(lat, lon)
        icon_code = data['weather'][0]['icon']
        weather_info = {
            'temperature': data['main']['temp'],
            'temp_min': data['main']['temp_min'],
            'temp_max': data['main']['temp_max'],
            'humidity': data['main']['humidity'],
            'weather_desc': data['weather'][0]['description'],
            'wind': data['wind'],
            'icon': icon_code,
            'icon_class': get_weather_icon_class(icon_code),  
            'unit': '°F' if unit == 'imperial' else '°C',
            'aqi': aqi_data,
            'tips': get_weather_tip(data['weather'][0]['description'], 
                                  data['main']['temp'], 
                                  data['main']['humidity'], 
                                  data['wind']['speed'], 
                                  unit),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return weather_info
    except Exception as e:
        print(f"Error in get_weather_by_coords: {e}")
        return None

def get_five_day_forecast_by_coords(lat, lon, unit='imperial'):
    """Get 5-day weather forecast data using coordinates."""
    url = f'http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units={unit}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get('cod') != '200':
            return None
        forecast = process_five_day_forecast(data, unit)
        return forecast
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
    return None

def format_city_name(city, state, country):
    """Format city name with state and country information."""
    parts = [city]
    if state:
        parts.append(state)
    if country:
        parts.append(country)
    return ", ".join(parts)

def get_weather_icon_class(icon_code):
    """Map OpenWeatherMap icon codes to Font Awesome classes"""
    icon_map = {
        '01d': 'fa-sun',           
        '01n': 'fa-sun',         
        '02d': 'fa-cloud-sun',     
        '02n': 'fa-cloud-sun',     
        '03d': 'fa-cloud',         
        '03n': 'fa-cloud',
        '04d': 'fa-cloud',         
        '04n': 'fa-cloud',
        '09d': 'fa-cloud-showers-heavy',  
        '09n': 'fa-cloud-showers-heavy',
        '10d': 'fa-cloud-rain',    
        '10n': 'fa-cloud-rain',
        '11d': 'fa-bolt',          
        '11n': 'fa-bolt',
        '13d': 'fa-snowflake',     
        '13n': 'fa-snowflake',
        '50d': 'fa-smog',         
        '50n': 'fa-smog'
    }
    return icon_map.get(icon_code, 'fa-question')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)