import time
import io
import os
import snowflake.connector
import pandas as pd
from flask import Flask, request, jsonify, Response
from pymongo.mongo_client import MongoClient
from snowflake.connector import DictCursor
from cryptography.fernet import Fernet
from pymongo.server_api import ServerApi
from cachetools import TTLCache
from dotenv import load_dotenv

# Here the in-memory time-based caches are set up
chart_data_cache = TTLCache(maxsize=100, ttl=1000)
time_series_cache = TTLCache(maxsize=100, ttl=1000)
clustering_cache = TTLCache(maxsize=100, ttl=1000)

# ======== Please put the decryption key provided in the report here ==========
decryption_key = b""
# =============================================================================

cipher_suite = Fernet(decryption_key)
with open(".env.enc", "rb") as file:
    encrypted_data = file.read()
decrypted_data = cipher_suite.decrypt(encrypted_data)
load_dotenv(stream=io.StringIO(decrypted_data.decode()))

# A separate MongoDB user has been created with a simple read/write access to a single relevant cluster
app = Flask(__name__)
uri = "mongodb+srv://evaluatoruser:evaluatorpass@cluster.hhoqbgj.mongodb.net/?retryWrites=true&w=majority"
mongo_client = MongoClient(uri, server_api=ServerApi('1'))
mongo_db = mongo_client['ProjectDB']
comments_collection = mongo_db['Comments']
users_collection = mongo_db['Users']

# Snowflake connection parameters that are taken from environmental variables. Will cause a crash without the correct decryption key
snowflake_config = {
    'user': os.getenv("SNOWFLAKE_USER"),
    'password': os.getenv("SNOWFLAKE_PASSWORD"),
    'account': os.getenv("SNOWFLAKE_ACCOUNT"),
    'warehouse': os.getenv("SNOWFLAKE_WAREHOUSE"),
    'database': os.getenv("SNOWFLAKE_DATABASE"),
    'schema': os.getenv("SNOWFLAKE_SCHEMA")
}


# This endpoint ensures the saving of a commentor's username to MongoDB
@app.route('/api/save_username', methods=['POST'])
def save_username():
    data = request.json
    username = data['username']

    if not users_collection.find_one({'_id': username}):
        users_collection.insert_one({'_id': username})

    return jsonify({'message': 'Username saved successfully'})


# This endpoint ensures the saving of a comment added to a chart to MongoDB
@app.route('/api/add_comment', methods=['POST'])
def add_comment():
    data = request.json
    chart_id = data['chart_id']
    comment_text = data['comment_text']
    user_id = data['user_id']

    comment = {
        'chart_id': chart_id,
        'user_id': user_id,
        'comment_text': comment_text
    }
    comments_collection.insert_one(comment)

    return jsonify({'message': 'Comment added successfully'})


# This endpoint extracts the comments for MongoDB for the relevant chart
@app.route('/api/get_comments', methods=['GET'])
def get_comments():
    chart_id = request.args.get('chart_id')
    comments = list(comments_collection.find({'chart_id': chart_id}, {'_id': 0}))

    return jsonify(comments)


# This is the bread and butter of the API. Ensures the correct query executed or the correct data is taken from the cache to be displayed in the interactive web dashboard
@app.route('/api/generate_chart', methods=['POST'])
def generate_chart():
    start_time = time.time()
    data = request.json
    selected_option = data['selected_option']
    cache_key = f"chart_data_{selected_option}"

    if cache_key in chart_data_cache:
        print("Cache hit!")
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Execution time: {elapsed_time:.4f} seconds")
        return jsonify(chart_data_cache[cache_key])

    print("Cache miss, querying Snowflake...")
    conn = snowflake.connector.connect(**snowflake_config)
    cursor = conn.cursor()

    if selected_option == '1':
        query = """
            SELECT DATE, CASES_WEEKLY 
            FROM ECDC_GLOBAL_WEEKLY 
            WHERE CASES_WEEKLY IS NOT NULL AND DATE IS NOT NULL
            """
        chart_title = "Global Cases Weekly (ECDC)"
        x_axis_title = "Date"
        y_axis_title = "Weekly cases"
    elif selected_option == '2':
        query = """
            SELECT DATE, DEATHS_WEEKLY 
            FROM ECDC_GLOBAL_WEEKLY 
            WHERE DEATHS_WEEKLY IS NOT NULL AND DATE IS NOT NULL
            """
        chart_title = "Global Deaths Weekly (ECDC)"
        x_axis_title = "Date"
        y_axis_title = "Weekly deaths"
    elif selected_option == '3':
        query = """
            SELECT CASES_WEEKLY, DEATHS_WEEKLY  
            FROM ECDC_GLOBAL_WEEKLY
            WHERE DEATHS_WEEKLY IS NOT NULL AND CASES_WEEKLY IS NOT NULL
            """
        chart_title = "Global Deaths vs. Cases (ECDC)"
        x_axis_title = "Cases"
        y_axis_title = "Deaths"
    elif selected_option == '4':
        query = """
            SELECT DATE, SUM(POSITIVE) AS POSITIVE
            FROM CDC_TESTING
            GROUP BY DATE
            ORDER BY DATE
            """
        chart_title = "Positive Test Results (CDC)"
        x_axis_title = "Date"
        y_axis_title = "Positive results"
    elif selected_option == '5':
        query = """
            SELECT DATE, SUM(NEGATIVE) AS POSITIVE
            FROM CDC_TESTING
            GROUP BY DATE
            ORDER BY DATE
            """
        chart_title = "Negative Test Results (CDC)"
        x_axis_title = "Date"
        y_axis_title = "Negative results"
    elif selected_option == '6':
        query = """
        WITH TotalDeaths AS (
            SELECT ISO3166_1, SUM(DEATHS) AS TOTAL_DEATHS
            FROM ECDC_GLOBAL
            WHERE DEATHS IS NOT NULL
            GROUP BY ISO3166_1
        ),
        RichestCountries AS (
            SELECT COUNTRY, GDP_PER_CAPITA
            FROM SUPPLEMENTARY.PUBLIC.RICHEST_COUNTRIES
        )
        SELECT RC.GDP_PER_CAPITA, TD.TOTAL_DEATHS
        FROM TotalDeaths TD
        JOIN RichestCountries RC ON TD.ISO3166_1 = RC.COUNTRY
        ORDER BY RC.GDP_PER_CAPITA;
        """
        chart_title = "COVID Deaths by GDP per capita"
        x_axis_title = "GDP per capita"
        y_axis_title = "Total deaths"

    cursor.execute(query)
    data = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(data, columns=column_names)

    x_data = df.iloc[:, 0].tolist()
    y_data = df.iloc[:, 1].tolist()

    chart_data = {
        'title': chart_title,
        'x_axis_title': x_axis_title,
        'y_axis_title': y_axis_title,
        'x': x_data,
        'y': y_data
    }

    if 'DATE' in df.columns:
        chart_data['x'] = [date.strftime('%Y-%m-%d') for date in chart_data['x']]

    chart_data_cache[cache_key] = chart_data

    conn.close()
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Execution time: {elapsed_time:.4f} seconds")

    return jsonify(chart_data)


# This endpoint is responsible for getting the relevant data for the time series prediction
@app.route('/api/time_series_data', methods=['GET'])
def get_time_series_data():
    start_time = time.time()
    cache_key = "time_series_data"

    if cache_key in time_series_cache:
        print("Cache hit for time_series_data!")
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Execution time: {elapsed_time:.4f} seconds")
        return Response(time_series_cache[cache_key], content_type='application/json')

    print("Cache miss for time_series_data, querying Snowflake...")
    conn = snowflake.connector.connect(**snowflake_config)
    cursor = conn.cursor()
    try:
        query = """
            SELECT DATE, SUM(CASES_WEEKLY) AS TOTAL_CASES
            FROM ECDC_GLOBAL_WEEKLY
            GROUP BY DATE
            ORDER BY DATE
        """

        cursor.execute(query)
        data = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(data, columns=column_names)

        response = df.to_json(date_format='iso', orient='split')

        time_series_cache[cache_key] = response

        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Execution time: {elapsed_time:.4f} seconds")

        return Response(response, content_type='application/json')
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "An error occurred while fetching data"}), 500
    finally:
        cursor.close()
        conn.close()


# This endpoint is resposible for getting the relevant date for clusterization
@app.route('/api/clustering_data', methods=['GET'])
def get_clustering_data():
    start_time = time.time()
    cache_key = "cluster_data"

    if cache_key in clustering_cache:
        print("Cache hit for cluster_data!")
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Execution time: {elapsed_time:.4f} seconds")
        return Response(clustering_cache[cache_key], content_type='application/json')

    print("Cache miss for cluster_data, querying Snowflake...")
    conn = snowflake.connector.connect(**snowflake_config)
    cursor = conn.cursor(DictCursor)
    try:
        query = """
            SELECT COUNTRY_REGION, CONTINENTEXP, SUM(CASES_WEEKLY) AS TOTAL_CASES, 
                   SUM(DEATHS_WEEKLY) AS TOTAL_DEATHS, AVG(POPULATION) AS AVG_POPULATION
            FROM ECDC_GLOBAL_WEEKLY
            GROUP BY COUNTRY_REGION, CONTINENTEXP
            ORDER BY TOTAL_CASES DESC
        """

        cursor.execute(query)
        data = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(data, columns=column_names)

        response = df.to_json(date_format='iso', orient='split')

        clustering_cache[cache_key] = response

        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Execution time: {elapsed_time:.4f} seconds")

        return Response(response, content_type='application/json')
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "An error occurred while fetching data"}), 500
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    app.run()
