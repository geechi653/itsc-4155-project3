from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

# OpenWeatherMap API key
API_KEY = '983e0f4c72e18f96cfe6e16ac315c528'

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        city = request.form['city']
        weather_data = get_weather(city)
        if weather_data is not None:
            return render_template('search.html', weather=weather_data, city=city)
        else:
            return render_template('search.html', city=city, error="City not found.")
    return render_template('search.html')

@app.route('/forecast', methods=['GET', 'POST'])
def forecast():
    if request.method == 'POST':
        city = request.form['city']
        forecast_data = get_five_day_forecast(city)
        return render_template('forecast.html', forecast=forecast_data, city=city)
    return render_template('forecast.html')

@app.route('/map')
def map():
    return render_template('map.html')

@app.route('/get_temperature_data')
def get_temperature_data():
    lat = request.args.get('lat', 0)
    lon = request.args.get('lon', 0)
    url = f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=imperial'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return jsonify({'temperature': data['main']['temp']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_weather(city):
    """Get current weather data using city name."""
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=imperial'
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
            'wind': data['wind']
        }  
        return weather_info
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
    return None

def get_five_day_forecast(city):
    """Get 5-day weather forecast data using city name."""
    url = f'http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=imperial'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get('cod') != '200':
            return None
        forecast = process_five_day_forecast(data)
        return forecast
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
    return None

def process_five_day_forecast(data):
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
                'wind_speeds': []
            }
        
        daily_forecast[date_str]['temperatures'].append(item['main']['temp'])
        daily_forecast[date_str]['weather_descriptions'].append(item['weather'][0]['description'])
        daily_forecast[date_str]['humidity'].append(item['main']['humidity'])
        daily_forecast[date_str]['wind_speeds'].append(item['wind']['speed'])
    
    forecast_summary = []
    for date, values in daily_forecast.items():
        avg_temp = sum(values['temperatures']) / len(values['temperatures'])
        avg_humidity = sum(values['humidity']) / len(values['humidity'])
        avg_wind_speed = sum(values['wind_speeds']) / len(values['wind_speeds'])
        common_description = max(set(values['weather_descriptions']), key=values['weather_descriptions'].count)
        
        forecast_summary.append({
            'date': date,
            'day_of_week': values['day_of_week'],
            'avg_temp': avg_temp,
            'avg_humidity': avg_humidity,
            'avg_wind_speed': avg_wind_speed,
            'description': common_description
        })
    
    return forecast_summary

if __name__ == '__main__':
    app.run(debug=True, port=8080)