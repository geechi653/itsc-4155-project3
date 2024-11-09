from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime
from functools import wraps
from time import time
from collections import defaultdict

app = Flask(__name__)

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
    unit = request.args.get('unit', 'imperial')
    return render_template('home.html', unit=unit)

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        city = request.form['city']
        unit = request.form.get('unit', 'imperial')
        weather_data = get_weather(city, unit)
        if weather_data is not None:
            return render_template('search.html', weather=weather_data, city=city, unit=unit)
        else:
            return render_template('search.html', city=city, error="City not found.", unit=unit)
    return render_template('search.html', unit=request.args.get('unit', 'imperial'))

@app.route('/forecast', methods=['GET', 'POST'])
def forecast():
    if request.method == 'POST':
        city = request.form['city']
        unit = request.form.get('unit', 'imperial')
        forecast_data = get_five_day_forecast(city, unit)
        return render_template('forecast.html', forecast=forecast_data, city=city, unit=unit)
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

def get_weather(city, unit='imperial'):
    """Get current weather data using city name."""
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units={unit}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get('cod') != 200:
            return None
        weather_info = {
            'temperature': data['main']['temp'],
            'temp_min': data['main']['temp_min'],
            'temp_max': data['main']['temp_max'],
            'humidity': data['main']['humidity'],
            'weather_desc': data['weather'][0]['description'],
            'wind': data['wind'],
            'icon': data['weather'][0]['icon'],
            'unit': '°F' if unit == 'imperial' else '°C',
            'tips': get_weather_tip(data['weather'][0]['description'], data['main']['temp'], data['main']['humidity'], data['wind']['speed'], unit)
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
    """Process the 5-day forecast data to group by day and get average temperature."""
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
                'icons': []
            }
        
        daily_forecast[date_str]['temperatures'].append(item['main']['temp'])
        daily_forecast[date_str]['weather_descriptions'].append(item['weather'][0]['description'])
        daily_forecast[date_str]['humidity'].append(item['main']['humidity'])
        daily_forecast[date_str]['wind_speeds'].append(item['wind']['speed'])
        daily_forecast[date_str]['icons'].append(item['weather'][0]['icon'])
    
    forecast_summary = []
    for date, values in daily_forecast.items():
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
    'unit': '°F' if unit == 'imperial' else '°C',
    'tips': get_weather_tip(common_description, avg_temp, avg_humidity, avg_wind_speed, unit)
})

        
    
    return forecast_summary

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)