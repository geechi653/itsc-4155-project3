from flask import Flask, render_template
import requests
from dotenv import load_dotenv
import os


app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def home():
    return "Weather App"

if __name__ == '__main__':
    app.run(debug=True)
