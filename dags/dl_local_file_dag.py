import os
from datetime import datetime
from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.bash import BashOperator
#from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator


PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BUCKET = os.environ.get("GCP_GCS_BUCKET")
URL ="https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={{ execution_date.strftime(\'%Y-%m-%d\') }}"

AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")
LOCAL_FILENAME = "{{ execution_date.strftime(\'%Y-%m-%d\') }}-equake.json"
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
        dst=LOCAL_FILENAME,
        bucket=f"{BUCKET}_{PROJECT_ID}",
    )

    wget_task >> upload_file
