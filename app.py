from flask import Flask, render_template, request, jsonify, url_for
import requests
from datetime import datetime
from functools import wraps
from time import time
from collections import defaultdict
from flask import session
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import redirect, flash

app = Flask(__name__)
app.secret_key = 'ee7ea1ebacf0f523ae4b3c285a59b34e'

def init_db():
    conn = sqlite3.connect('weather_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS search_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  city TEXT NOT NULL,
                  search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    

    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  first_name TEXT NOT NULL,
                  last_name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  phone_number TEXT,
                  password_hash TEXT NOT NULL)''')
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
    
 
    if unit == 'imperial':
        if temp > 85:
            tips.append("High temperature alert! Stay hydrated and seek shade when possible.")
        elif temp < 32:
            tips.append("Freezing conditions! Bundle up and watch for icy surfaces.")
    else:  # for celsius convrtedd from farenheit
        if temp > 29:
            tips.append("High temperature alert! Stay hydrated and seek shade when possible.")
        elif temp < 0:
            tips.append("Freezing conditions! Bundle up and watch for icy surfaces.")

   
    weather_desc = weather_desc.lower()
    if 'rain' in weather_desc:
        tips.append("Don't forget your umbrella and waterproof footwear!")
    elif 'snow' in weather_desc:
        tips.append("Snow expected! Dress warmly and drive carefully.")
    elif 'storm' in weather_desc or 'thunder' in weather_desc:
        tips.append("Stormy conditions! Stay indoors if possible and avoid open areas.")
    elif 'clear' in weather_desc:
        tips.append("Perfect weather for outdoor activities! Don't forget sunscreen.")
    elif 'cloud' in weather_desc:
        tips.append("Cloudy conditions - good for outdoor activities but keep an eye on changes.")

  
    if humidity > 70:
        tips.append("High humidity - stay hydrated and dress in breathable clothing.")
    elif humidity < 30:
        tips.append("Low humidity - remember to moisturize and stay hydrated.")

   
    if wind_speed > 10:
        tips.append("Strong winds! Secure loose objects and be careful when driving.")
    
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
    user_first_name = None
    logged_in = 0
    if 'user_id' in session:
        conn = sqlite3.connect('weather_history.db')
        c = conn.cursor()
        c.execute('SELECT first_name FROM users WHERE id = ?', (session['user_id'],))
        user = c.fetchone()
        conn.close()

        if user:
            user_first_name = user[0]
            logged_in = 1

    return render_template('home.html', user_first_name=user_first_name, logged_in=logged_in)

@app.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method == 'POST':
        first_name = request.form['first-name']
        last_name = request.form['last-name']
        email = request.form['email']
        phone_number = request.form['phone-number']
        password = request.form['password']

        password_hash = generate_password_hash(password)

        try:
            conn = sqlite3.connect('weather_history.db')
            c = conn.cursor()
            c.execute('INSERT INTO users (first_name, last_name, email, phone_number, password_hash) VALUES (?, ?, ?, ?, ?)',
                      (first_name, last_name, email, phone_number, password_hash))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered. Please log in.', 'error')
            return redirect(url_for('signup'))

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    logged_in = 0
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    logged_in = 0
    if request.method == 'POST':
        email = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('weather_history.db')
        c = conn.cursor()
        c.execute('SELECT id, password_hash FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
            logged_in = 1
        else:
            flash('Invalid email or password. Please try again.', 'error')

    return render_template('login.html', logged_in=logged_in)

@app.route('/search', methods=['GET', 'POST'])
def search():
    logged_in = 0
    if 'user_id' in session:
        logged_in = 1

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
    return render_template('search.html', unit=request.args.get('unit', 'imperial'), history=history, logged_in=logged_in)

@app.route('/forecast', methods=['GET', 'POST'])
def forecast():
    logged_in = 0
    if 'user_id' in session:
        logged_in = 1

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

    return render_template('forecast.html', unit=request.args.get('unit', 'imperial'), logged_in=logged_in)

@app.route('/map')
def map():

    logged_in = 0
    if 'user_id' in session:
        logged_in = 1

    unit = request.args.get('unit', 'imperial')
    return render_template('map.html', unit=unit, logged_in=logged_in)

@app.route('/get_temperature_data')
@rate_limit()
def get_temperature_data():
    lat = request.args.get('lat', 0)
    lon = request.args.get('lon', 0)
    unit = request.args.get('unit', 'imperial')
    url = f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units={unit}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return jsonify({
            'temperature': data['main']['temp'],
            'unit': '°F' if unit == 'imperial' else '°C',
            'icon': data['weather'][0]['icon'],
            'description': data['weather'][0]['description']
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
        weather_info = {
            'temperature': data['main']['temp'],
            'temp_min': data['main']['temp_min'],
            'temp_max': data['main']['temp_max'],
            'humidity': data['main']['humidity'],
            'weather_desc': data['weather'][0]['description'],
            'wind': data['wind'],
            'icon': data['weather'][0]['icon'],
            'unit': '°F' if unit == 'imperial' else '°C',
            'aqi': aqi_data,
            'tips': get_weather_tip(data['weather'][0]['description'], data['main']['temp'], data['main']['humidity'], data['wind']['speed'], unit),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')  
        }  
        return weather_info
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
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
    daily_forecast = {}

    for item in data['list']:
        date_time = datetime.utcfromtimestamp(item['dt'])
        date_str = date_time.strftime('%Y-%m-%d')
        day_of_week = date_time.strftime('%A')  

        if date_str not in daily_forecast:
            daily_forecast[date_str] = {
                'day_of_week': day_of_week,
                'temperatures': [],
                'weather_descriptions': [],
                'humidity': [],
                'wind_speeds': [],
                'icons': [],
                'lat': data['city']['coord']['lat'],
                'lon': data['city']['coord']['lon']
            }

        daily_forecast[date_str]['temperatures'].append(item['main']['temp'])
        daily_forecast[date_str]['weather_descriptions'].append(item['weather'][0]['description'])
        daily_forecast[date_str]['humidity'].append(item['main']['humidity'])
        daily_forecast[date_str]['wind_speeds'].append(item['wind']['speed'])
        daily_forecast[date_str]['icons'].append(item['weather'][0]['icon'])

    forecast_summary = []
    for date, values in daily_forecast.items():
        aqi_data = get_aqi(values['lat'], values['lon'])
        avg_temp = sum(values['temperatures']) / len(values['temperatures'])
        avg_humidity = sum(values['humidity']) / len(values['humidity'])
        avg_wind_speed = sum(values['wind_speeds']) / len(values['wind_speeds'])
        common_description = max(set(values['weather_descriptions']), key=values['weather_descriptions'].count)
        common_icon = max(set(values['icons']), key=values['icons'].count)

        forecast_summary.append({
            'date': date,
            'day_of_week': values['day_of_week'],
            'avg_temp': avg_temp,
            'avg_humidity': avg_humidity,
            'avg_wind_speed': avg_wind_speed,
            'description': common_description,
            'icon': common_icon,
            'aqi': aqi_data,
            'unit': '°F' if unit == 'imperial' else '°C',
            'tips': get_weather_tip(common_description, avg_temp, avg_humidity, avg_wind_speed, unit),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')  
        })

    return forecast_summary

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
        weather_info = {
            'temperature': data['main']['temp'],
            'temp_min': data['main']['temp_min'],
            'temp_max': data['main']['temp_max'],
            'humidity': data['main']['humidity'],
            'weather_desc': data['weather'][0]['description'],
            'wind': data['wind'],
            'icon': data['weather'][0]['icon'],
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
        print(f"Error: {e}")
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)