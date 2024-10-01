import requests

def get_weather(city_name):
    api_key = 'cbbf74229c802cbf4e0cb4172a6112d4'
    base_url = 'http://api.openweathermap.org/data/2.5/weather?'
    complete_url = base_url + 'q=' + city_name + '&appid=' + api_key + '&units=metric'
    
    response = requests.get(complete_url)
    
    if response.status_code == 200:
        data = response.json()
        main = data['main']
        wind = data['wind']
        weather_description = data['weather'][0]['description']
        
        print(f"Temperature: {main['temp']}°C")
        print(f"Humidity: {main['humidity']}%")
        print(f"Wind Speed: {wind['speed']} m/s")
        print(f"Weather Description: {weather_description}")
    else:
        print("City not found.")

city = input("Enter city name: ")
get_weather(city)
