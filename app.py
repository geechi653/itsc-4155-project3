from flask import Flask, render_template, request
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
            'wind': data['wind'],
            'icon' : data['weather'][0]['icon']
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
        # Conversion to get the day of the week displayed
        date_time = datetime.utcfromtimestamp(item['dt'])
        date_str = date_time.strftime('%Y-%m-%d')
        day_of_week = date_time.strftime('%A')  
        
        # Initializes a new entry for each day
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
    
    # Calculates the daily averages and most common descriptions
    forecast_summary = []
    for date, values in daily_forecast.items():
        avg_temp = sum(values['temperatures']) / len(values['temperatures'])
        avg_humidity = sum(values['humidity']) / len(values['humidity'])
        avg_wind_speed = sum(values['wind_speeds']) / len(values['wind_speeds'])
        common_description = max(set(values['weather_descriptions']), key=values['weather_descriptions'].count)
        common_icon = values['icons'][0]

        forecast_summary.append({
            'date': date,
            'day_of_week': values['day_of_week'],  # Add day of the week to the summary
            'avg_temp': avg_temp,
            'avg_humidity': avg_humidity,
            'avg_wind_speed': avg_wind_speed,
            'description': common_description,
            'icon': common_icon
        })
    
    return forecast_summary
if __name__ == '__main__':
    app.run(debug=True)
