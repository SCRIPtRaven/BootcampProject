import json
import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import matplotlib.pyplot as plt
import sys
import requests


def fetch_data_from_api():
    try:
        response = requests.get('http://127.0.0.1:5000/api/time_series_data')

        if response.status_code == 200:
            response_json = response.json()
            df = pd.read_json(json.dumps(response_json), orient='split')
            return df
        else:
            print(f"Failed to get data from API. HTTP Status Code: {response.status_code}")
            sys.exit(1)

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(2)


def holt_winters_forecast(df):
    df['DATE'] = pd.to_datetime(df['DATE'])
    df.set_index('DATE', inplace=True)

    # Here you can select a cutoff date from which to make a prediction (Do note that if the cutoff date is right at a big change, the model might not work due to the time's chaotic nature
    # cutoff_date = '2023-01-01'
    # df = df[df.index <= pd.Timestamp(cutoff_date)]

    df.index.freq = 'W-MON'

    model = ExponentialSmoothing(df['TOTAL_CASES'], seasonal='add', seasonal_periods=52, use_boxcox=True)
    model_fit = model.fit(remove_bias=True, use_brute=True)

    future_steps = 50
    forecast = model_fit.forecast(steps=future_steps)
    forecast = np.maximum(forecast, 0)

    plt.figure(figsize=(12, 6))
    plt.plot(df['TOTAL_CASES'], label='Observed')
    plt.plot(pd.date_range(df.index[-1], periods=future_steps + 1, freq='W-MON')[1:], forecast, label='Forecast',
             color='red')
    plt.ticklabel_format(style='plain', axis='y')
    plt.xticks(rotation=45)
    plt.subplots_adjust(bottom=0.2)
    plt.locator_params(axis='x', nbins=6)
    plt.legend()
    plt.show()


if __name__ == '__main__':
    df = fetch_data_from_api()
    holt_winters_forecast(df)
