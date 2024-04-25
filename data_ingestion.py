
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator, BigQueryCreateEmptyTableOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta, timezone
import requests
import os
import pandas as pd
from google.cloud import storage
from airflow.providers.google.cloud.hooks.gcs import GCSHook



API_KEY = Variable.get("weather-api-key")
GCS_BUCKET = Variable.get("gcs-bucket")
PROJECT_ID = Variable.get("bq_data_warehouse_project")

BQ_DATASET = "weather"
BQ_STAGING_DATASET = f"stg_{BQ_DATASET}"
TABLE_NAME = 'daily_data'
SQL_PATH = f"{os.path.abspath(os.path.dirname(__file__))}/sql/"
LAT = 40.7128  # Example: New York City latitude
LON = -74.0060  # Example: New York City longitude




default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'backfill_date': datetime.strptime('2024-03-02', '%Y-%m-%d').date()
}

def date_to_unix_timestamp(date):

    if date is None:
    # Get the current date
        date = datetime.now().date()

    # Convert to a datetime object with time set to midnight
    date_converted = datetime.combine(date, datetime.min.time())
    
    # Convert to Unix timestamp (UTC time zone)
    unix_timestamp = int(date_converted.replace(tzinfo=timezone.utc).timestamp())
    
    return unix_timestamp, date


def fetch_weather_data(**context):
    backfill_date = default_args['backfill_date']
    unix_timestamp, date = date_to_unix_timestamp(backfill_date)
    url = f"https://api.openweathermap.org/data/3.0/onecall/timemachine?lat={LAT}&lon={LON}&dt={unix_timestamp}&appid={API_KEY}"

    # Make the request
    response = requests.get(url)
    data = response.json()["data"]
    df = pd.DataFrame(data)

    # Create an extra column, datetime non-unix timestamp format
    df['datetime'] = date

    # Save DataFrame to Parquet
    filename = f"weather_data_{date}.parquet"
    """
    Push the filename into Xcom - XCom (short for cross-communication) is a 
    mechanism that allows tasks to exchange messages or small amounts of data.
    Variable have a function scope, but we need to use it in the next task
    """
    context['ti'].xcom_push(key='filename', value=filename)

    # Upload the file
    gcs_hook = GCSHook() # it's using default GCP conection 'google_cloud_default'
    gcs_hook.upload(bucket_name=GCS_BUCKET, object_name=filename, data=df.to_parquet(index=False))




dag = DAG(
    'weather_data_ingestion',
    default_args=default_args,
    description='Fetch weather data and store in BigQuery',
    schedule_interval='@daily',
)

fetch_weather_data_task = PythonOperator(
    task_id='fetch_weather_data',
    python_callable=fetch_weather_data,
    dag=dag,
)


gcs_to_bq_staging_task = GCSToBigQueryOperator(
    task_id="gcs_to_bigquery",
    bucket=GCS_BUCKET,
    source_objects=["{{ti.xcom_pull(key='filename')}}"], # pull filename from Xcom from the previous task
    destination_project_dataset_table=f'{PROJECT_ID}.{BQ_STAGING_DATASET}.stg_{TABLE_NAME}',
    create_disposition='CREATE_IF_NEEDED', # automatically creates table for us
    write_disposition='WRITE_TRUNCATE', # automatically drops previously stored data in the table
    time_partitioning={'type': 'DAY', 'field': 'datetime'}, # remember partitioning in the beginning? here it comes!
    gcp_conn_id="google_cloud_default",
    source_format='PARQUET',
    dag=dag,
)


create_table_with_schema = BigQueryCreateEmptyTableOperator(
    task_id='create_table_with_schema',
    project_id=PROJECT_ID,
    dataset_id=BQ_DATASET,
    table_id=TABLE_NAME,
    time_partitioning={'type': 'DAY', 'field': 'datetime'},
    schema_fields=[
        {"name": "dt", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "sunrise", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "sunset", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "temp", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "feels_like", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "pressure", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "humidity", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "dew_point", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "clouds", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "visibility", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "wind_speed", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "wind_deg", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "weather", "type": "RECORD", "mode": "NULLABLE", "fields": [
            {"name": "list", "type": "RECORD", "mode": "REPEATED", "fields": [
                {"name": "element", "type": "RECORD", "mode": "NULLABLE", "fields": [
                    {"name": "description", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "icon", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "main", "type": "STRING", "mode": "NULLABLE"}
                ]}
            ]}
        ]},
        {"name": "datetime", "type": "DATE", "mode": "NULLABLE"}
    ],
    dag=dag,
)


stg_to_prod_task = BigQueryInsertJobOperator(
    task_id=f"upsert_staging_to_prod_task",
    project_id=PROJECT_ID,
    configuration={
        "query": {
                    "query": open(f"{SQL_PATH}upsert_table.sql", 'r').read()
                    .replace('{project_id}', PROJECT_ID)
                    .replace('{bq_dataset}', BQ_DATASET)
                    .replace('{table_name}', TABLE_NAME),
                    # .replace('{partition_date}', date.today().isoformat()),
                    "useLegacySql": False
                },
                "createDisposition": "CREATE_IF_NEEDED",
                 "destinationTable": {
                        "project_id": PROJECT_ID,
                        "dataset_id": BQ_DATASET,
                        "table_id": TABLE_NAME
                    }
    },
    dag=dag
)


fetch_weather_data_task >> gcs_to_bq_staging_task >> create_table_with_schema >> stg_to_prod_task
