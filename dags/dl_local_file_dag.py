import os

# from datetime import datetime
from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.bash import BashOperator

# from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.transfers.local_to_gcs import (
    LocalFilesystemToGCSOperator,
)

from airflow.providers.google.cloud.transfers.gcs_to_bigquery import (
    GCSToBigQueryOperator,
)

from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryCreateEmptyTableOperator,
)

from airflow.providers.google.cloud.operators.gcs import (
    GCSFileTransformOperator,
)
from airflow.contrib.operators.bigquery_operator import BigQueryOperator

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BUCKET = os.environ.get("GCP_GCS_BUCKET")
BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query?"
QUERY = "format=geojson&starttime={{ execution_date.strftime('%Y-%m-%d') }}"
URL = BASE_URL + QUERY

AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")
LOCAL_FILENAME = "{{ execution_date.strftime('%Y-%m-%d-%H-%M') }}-equake.json"
LOCAL_FILENAME_CSV = LOCAL_FILENAME.replace(".json", ".csv")
LOCAL_FILEPATH = os.path.join(AIRFLOW_HOME, LOCAL_FILENAME)
BUCKET_PATH = f"gs://{BUCKET}_{PROJECT_ID}/"

SCHEMA_FIELDS = [
    {"name": "id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "mag", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "place", "type": "STRING", "mode": "NULLABLE"},
    {"name": "time", "type": "DATETIME", "mode": "NULLABLE"},
    {"name": "updated", "type": "DATETIME", "mode": "NULLABLE"},
    {"name": "tz", "type": "STRING", "mode": "NULLABLE"},
    {"name": "url", "type": "STRING", "mode": "NULLABLE"},
    {"name": "detail", "type": "STRING", "mode": "NULLABLE"},
    {"name": "felt", "type": "STRING", "mode": "NULLABLE"},
    {"name": "cdi", "type": "STRING", "mode": "NULLABLE"},
    {"name": "mmi", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "alert", "type": "STRING", "mode": "NULLABLE"},
    {"name": "status", "type": "STRING", "mode": "NULLABLE"},
    {"name": "tsunami", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "sig", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "net", "type": "STRING", "mode": "NULLABLE"},
    {"name": "code", "type": "STRING", "mode": "NULLABLE"},
    {"name": "ids", "type": "STRING", "mode": "NULLABLE"},
    {"name": "sources", "type": "STRING", "mode": "NULLABLE"},
    {"name": "types", "type": "STRING", "mode": "NULLABLE"},
    {"name": "nst", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "dmin", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "rms", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "gap", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "magType", "type": "STRING", "mode": "NULLABLE"},
    {"name": "type", "type": "STRING", "mode": "NULLABLE"},
    {"name": "title", "type": "STRING", "mode": "NULLABLE"},
    {"name": "geometry", "type": "GEOGRAPHY", "mode": "NULLABLE"},
]

BQ_STAGING = f"{PROJECT_ID}.equake_data.staging_geo_json"
BQ_WAREHOUSE = f"{PROJECT_ID}.equake_data.geo_json"
# https://medium.com/bakdata/data-warehousing-made-easy-with-google-bigquery-and-apache-airflow-bf62e6c727ed


def _create_merge_sql(source, target, schema, **context):
    columns = [item["name"] for item in schema]
    columns = ",".join(columns)
    return f"""
        MERGE `{target}` T
        USING `{source}` S
        ON T.cdc_hash = TO_BASE64(MD5(TO_JSON_STRING(S)))
        WHEN NOT MATCHED THEN
          INSERT ({columns}, inserted_at, cdc_hash)
          VALUES ({columns}, CURRENT_DATETIME(),
          TO_BASE64(MD5(TO_JSON_STRING(S))))
    """


default_args = {
    "owner": "airflow",
    "start_date": days_ago(1),
    "depends_on_past": False,
    "retries": 1,
}
# NOTE: DAG declaration - using a Context Manager (an implicit way)
with DAG(
    dag_id="data_ingestion_gcs_dag",
    schedule_interval="@hourly",
    default_args=default_args,
    catchup=False,
    max_active_runs=1,
    tags=["dtc-de"],
) as dag:
    wget = BashOperator(
        task_id="wget", bash_command=f'curl -sSL "{URL}" -o {LOCAL_FILEPATH}'
    )

    upload_file = LocalFilesystemToGCSOperator(
        task_id="upload_file",
        src=LOCAL_FILEPATH,
        dst=f"raw/{LOCAL_FILENAME}",
        bucket=f"{BUCKET}_{PROJECT_ID}",
    )

    remove_local_file = BashOperator(
        task_id="remove_local_file", bash_command=f"rm {LOCAL_FILEPATH}"
    )

    transform_json = GCSFileTransformOperator(
        task_id="transform_json",
        source_bucket=f"{BUCKET}_{PROJECT_ID}",
        source_object=f"raw/{LOCAL_FILENAME}",
        destination_bucket=None,
        destination_object=f"pre-processed/{LOCAL_FILENAME_CSV}",
        transform_script=("/opt/airflow/dags/transform_json_to_csv.py"),
    )

    load_csv_to_bq = GCSToBigQueryOperator(
        task_id="load_csv_to_bq",
        bucket=f"{BUCKET}_{PROJECT_ID}",
        source_objects=f"pre-processed/{LOCAL_FILENAME_CSV}",
        source_format="CSV",
        skip_leading_rows=1,
        destination_project_dataset_table=BQ_STAGING,
        write_disposition="WRITE_TRUNCATE",
        schema_fields=SCHEMA_FIELDS,
    )

    create_prod_table = BigQueryCreateEmptyTableOperator(
        task_id="create_prod_table",
        dataset_id="equake_data",
        table_id="geo_json",
        project_id=PROJECT_ID,
        schema_fields=SCHEMA_FIELDS
        + [
            {"name": "cdc_hash", "type": "STRING"},
            {"name": "inserted_at", "type": "DATETIME"},
        ],
        exists_ok=True,
    )

    merge_into_warehouse = BigQueryOperator(
        task_id="merge_into_warehouse",
        sql=_create_merge_sql(BQ_STAGING, BQ_WAREHOUSE, SCHEMA_FIELDS),
        use_legacy_sql=False,
    )
    # BASH_COMMAND = f"
    # bq load --source_format=NEWLINE_DELIMITED_JSON
    # --json_extension=GEOJSON
    # --autodetect equake_data.geojson_airflow pre-processed/{LOCAL_FILENAME}"

    # load_geojson_to_bq = BashOperator(
    #    task_id="load_geo_to_bq",
    #    bash_command=BASH_COMMAND)

    (
        wget
        >> upload_file
        >> remove_local_file
        >> transform_json
        >> load_csv_to_bq
        >> create_prod_table
        >> merge_into_warehouse
    )
