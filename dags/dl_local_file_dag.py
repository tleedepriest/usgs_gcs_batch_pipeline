import os
from datetime import datetime
from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.bash import BashOperator
#from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.providers.google.cloud.operators.gcs import GCSFileTransformOperator
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BUCKET = os.environ.get("GCP_GCS_BUCKET")
URL ="https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={{ execution_date.strftime(\'%Y-%m-%d\') }}"

AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")
LOCAL_FILENAME = "{{ execution_date.strftime(\'%Y-%m-%d-%H-%M\') }}-equake.json"
LOCAL_FILENAME_CSV = LOCAL_FILENAME.replace('.json', '.csv')
LOCAL_FILEPATH = os.path.join(AIRFLOW_HOME, LOCAL_FILENAME)
BUCKET_PATH = f"gs://{BUCKET}_{PROJECT_ID}/"


default_args = {
    "owner": "airflow",
    "start_date": days_ago(1),
    "depends_on_past": False,
    "retries": 1,
}
# NOTE: DAG declaration - using a Context Manager (an implicit way)
with DAG(
    dag_id="data_ingestion_gcs_dag",
    schedule_interval="@daily",
    default_args=default_args,
    catchup=False,
    max_active_runs=1,
    tags=['dtc-de'],
) as dag:
    wget_task = BashOperator(
        task_id='wget',
        bash_command=f'curl -sSL "{URL}" -o {LOCAL_FILEPATH}'
    )

    upload_file = LocalFilesystemToGCSOperator(
        task_id="upload_file",
        src=LOCAL_FILEPATH,
        dst=f"raw/{LOCAL_FILENAME}",
        bucket=f"{BUCKET}_{PROJECT_ID}",
    )

    transform_json = GCSFileTransformOperator(
        task_id="transform_json",
        source_bucket=f"{BUCKET}_{PROJECT_ID}",
        source_object=f"raw/{LOCAL_FILENAME}",
        destination_bucket=None,
        destination_object=f"pre-processed/{LOCAL_FILENAME_CSV}",
        transform_script="/opt/airflow/dags/transform_json_to_new_line_json.py"
    )

    load_csv_to_bq = GCSToBigQueryOperator(
        task_id="load_csv_to_bq",
        bucket=f"{BUCKET}_{PROJECT_ID}",
        source_objects=f"pre-processed/{LOCAL_FILENAME_CSV}",
        source_format="CSV",
        skip_leading_rows=1,
        destination_project_dataset_table=f"{PROJECT_ID}.equake_data.from_csv",
        write_disposition="WRITE_APPEND",
        schema_fields=[
        {'name': 'id', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'mag', 'type': 'FLOAT', 'mode': 'NULLABLE'},
        {'name': 'place', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'time', 'type': 'DATETIME', 'mode': 'NULLABLE'},
        {'name': 'updated', 'type': 'DATETIME', 'mode': 'NULLABLE'},
        {'name': 'tz', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'url', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'detail', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'felt', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'cdi', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'mmi', 'type': 'FLOAT', 'mode': 'NULLABLE'},
        {'name': 'alert', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'status', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'tsunami', 'type': 'INTEGER', 'mode': 'NULLABLE'},
        {'name': 'sig', 'type': 'INTEGER', 'mode': 'NULLABLE'},
        {'name': 'net', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'code', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'ids', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'sources', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'types', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'nst', 'type': 'FLOAT', 'mode': 'NULLABLE'},
        {'name': 'dmin', 'type': 'FLOAT', 'mode': 'NULLABLE'},
        {'name': 'rms', 'type': 'FLOAT', 'mode': 'NULLABLE'},
        {'name': 'gap', 'type': 'FLOAT', 'mode': 'NULLABLE'},
        {'name': 'magType', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'type', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'title', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'geometry', 'type': 'GEOGRAPHY', 'mode': 'NULLABLE'}
    ]
    )
   # BASH_COMMAND = f"bq load --source_format=NEWLINE_DELIMITED_JSON --json_extension=GEOJSON --autodetect equake_data.geojson_airflow pre-processed/{LOCAL_FILENAME}"

    #load_geojson_to_bq = BashOperator(
    #    task_id="load_geo_to_bq",
    #    bash_command=BASH_COMMAND)

    wget_task >> upload_file >> transform_json >> load_csv_to_bq
