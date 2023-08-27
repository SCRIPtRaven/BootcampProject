from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import requests
import pandas as pd


def fetch_clustering_data():
    try:
        response = requests.get('http://127.0.0.1:5000/api/clustering_data')
        if response.status_code == 200:
            response_data = response.json()
            df = pd.DataFrame.from_records(response_data['data'], columns=response_data['columns'])
            return df
        else:
            print(f"Failed to get clustering data. HTTP Status Code: {response.status_code}")
            return None
    except Exception as e:
        print(f"An error occurred in getting data: {e}")
        return None


def cluster_countries(df):
    # Step 1: Feature Engineering
    df['CASES_PER_POPULATION'] = df['TOTAL_CASES'] / df['AVG_POPULATION']
    df['DEATHS_PER_POPULATION'] = df['TOTAL_DEATHS'] / df['AVG_POPULATION']

    # Step 2: Data Scaling
    selected_columns = ['CASES_PER_POPULATION', 'DEATHS_PER_POPULATION']
    df_cluster = df[selected_columns].dropna()

    scaler = StandardScaler()
    df_scaled = scaler.fit_transform(df_cluster)

    # Step 3: Number of clusters was chosen by an externally done elbow method chart
    optimal_k = 3

    # Step 4: Run K-means
    kmeans = KMeans(n_clusters=optimal_k, random_state=42)
    df['Cluster'] = kmeans.fit_predict(df_scaled)

    # Step 5: Analyze the Clusters
    print(f"Cluster Centers in Scaled Units: \n{kmeans.cluster_centers_}")
    print(f"\nCluster Distribution: \n{df['Cluster'].value_counts().to_string()}")

    return df


df = fetch_clustering_data()
if df is not None:
    clustered_df = cluster_countries(df)


# Based on these results we can see that countries were clustered into separate clusters with an even distribution
# We can also see that each cluster shows meaningful difference:
# Cluster 1: Countries with relatively low cases but a high amount of deaths, meaning it could've been countries that were smaller in nature and more isolated, but with poor preparation to fight the disease
# Cluster 2: Countries with high cases but low deaths, meaning it could've been countries that are large, but also have effective testing methods and a good healthcare to prevent deaths
# Cluster 3: Countries with both low cases and deaths, meaning it could've either been countries with very good healthcare or very isolated countries where COVID had little effect (Could also be countries that misreported their statistics)

'''
Cluster Centers in Scaled Units: 
[[ 0.04495599  1.04032039]
 [ 0.85492211 -0.65924359]
 [-1.09985101 -0.46576054]]

Cluster Distribution: 
Cluster
0    11
1    11
2     9
'''