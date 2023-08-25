from flask import Flask, request, jsonify
import snowflake.connector
import pandas as pd

app = Flask(__name__)

# Snowflake connection parameters
snowflake_config = {
    'user': 'Aivaras56',
    'password': 'Xeroniukas56',
    'account': 'elb80569',
    'warehouse': 'PROJECT_WH',
    'database': 'COVID19_EPIDEMIOLOGICAL_DATA',
    'schema': 'PUBLIC'
}


# Function to fetch data from Snowflake
def fetch_data():
    conn = snowflake.connector.connect(**snowflake_config)
    query = "SELECT * FROM WHO_SITUATION_REPORTS SAMPLE (25 ROWS)"
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]
    conn.close()
    df = pd.DataFrame(data, columns=column_names)
    return df


# API endpoint to get available columns
@app.route('/api/get_columns', methods=['GET'])
def get_columns():
    df = fetch_data()
    columns = df.columns.tolist()
    return jsonify(columns)


# API endpoint to get data for plotting
@app.route('/api/plot_data', methods=['POST'])
def plot_data():
    data = request.json
    x_col = data['x_column']
    y_col = data['y_column']

    df = fetch_data()
    plot_df = df[[x_col, y_col]]

    # Sort the DataFrame by y-column in descending order
    plot_df = plot_df.sort_values(by=y_col, ascending=False)

    plot_data = {
        'x': plot_df[x_col].tolist(),
        'y': plot_df[y_col].tolist()
    }
    return jsonify(plot_data)


if __name__ == '__main__':
    app.run(debug=True)