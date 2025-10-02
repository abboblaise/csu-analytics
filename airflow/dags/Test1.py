from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.models import BaseOperator, Variable
from airflow.operators.python_operator import PythonOperator
from airflow_hop.operators import HopPipelineOperator
from airflow.triggers.temporal import TimeDeltaTrigger
import logging
from datetime import datetime, timedelta
from airflow.utils.context import Context
from minio import Minio
from read_parquet_schema.parquet_functions import read_parquet_schema_for_druid
import requests
from requests.auth import HTTPBasicAuth
from superset.superset_client import SupersetClient
import urllib.parse
from typing import Dict, Any
import xml.etree.ElementTree as ET


task_logger = logging.getLogger('airflow.task')

default_args = {
    "owner": "admin",
    "depend_on_past": False,
    "start_date": datetime(2025, 7, 4),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5)
}

minio_url = Variable.get("minio_url")
minio_access_key = Variable.get("minio_access_key")
minio_secret_key = Variable.get("minio_secret_key")
minio_ftp_server = Variable.get("minio_ftp_server")
minio_ftp = f"{minio_access_key}:{minio_secret_key}@{minio_ftp_server}"

superset_base_url = Variable.get('superset_base_url')
repan_db_name = Variable.get('repan_db_name')

druid_admin_password = Variable.get('druid_admin_password')
druid_auth = HTTPBasicAuth('admin', druid_admin_password)
druid_coordinator_url = Variable.get('druid_coordinator_url')
druid_router_url = Variable.get('druid_router_url')

# This is a mandatory transformation to replace the parquet filename entered by the user with the correct one that can be processed by airflow
def update_parquet_filename_in_content(xml_content, new_filename):
    root = ET.fromstring(xml_content)
    
    for transform in root.findall("transform"):
        transform_type = transform.find("type")
        if transform_type is not None and transform_type.text == "ParquetFileOutput":
            filename_base = transform.find("filename_base")
            if filename_base is not None:
                filename_base.text = new_filename
    
    updated_content = ET.tostring(root, encoding="unicode")
    return updated_content

# Download pipeline from minio bucket
def download_pipeline_minio():
    task_logger.debug('Beginning download of pipeline from MinIO…')
    client = Minio(minio_url, access_key=minio_access_key , secret_key=minio_secret_key, secure=False)
    client.fget_object("pipelines","pipelines-created/8090433b-b56d-40fb-af22-785c89848787/test.hpl","/hop/config/projects/default/8090433b-b56d-40fb-af22-785c89848787/test.hpl")
    task_logger.info('Download of pipeline from MinIO completed')

    # Open the file in read-write mode to modify in place
    try:
        with open("/hop/config/projects/default/8090433b-b56d-40fb-af22-785c89848787/test.hpl", 'r+') as file:
            content = file.read()
            updated_content = content.replace("${PROJECT_HOME}", "/files/")
            # This is a mandatory transformation to replace the parquet filename entered by the user with the correct one that can be processed by airflow
            updated_content = update_parquet_filename_in_content(updated_content, "ftp://${minio_ftp}/parquets/${user_id}/${dag_display_name}")
            file.seek(0)
            file.write(updated_content)
            file.truncate()
    except Exception as e:
        task_logger.error(f"Error while modifying the file: {e}")
        raise AirflowException(f"Failed to replace string in pipeline file: {e}")

# Ingest to druid
class DruidOperator(BaseOperator):
  def __init__(self, **kwargs):
    super().__init__(task_id = 'repan_druid_ingestion', **kwargs)
    self.base_url = "{}/druid/indexer/v1/task".format(druid_coordinator_url)

  def execute(self, context: Context):
    timestamp_spec, schema = read_parquet_schema_for_druid(file = "Test1.parquet", path = "8090433b-b56d-40fb-af22-785c89848787")
    payload = {
      "type": "index_parallel",
      "spec": {
        "ioConfig": {
          "type": "index_parallel",
          "drop_existing": True,
          "inputSource": {
            "type": "s3",
            "endpointConfig": {
              "url": minio_url if minio_url.startswith("http://") else "http://{}".format(minio_url),
              # Even if MinIO does not have regions, this is required because the Se extensions use
              # AWS libraries under the hood which insist on getting a region
              "signingRegion": "us-east-1"
            },
            "clientConfig": {
              # Our internal communication is not encrypted, so use plain HTTP
              "protocol": "http",
              # Since we do not have the necessary DNS set up to use the sub-domain per bucket
              # scheme, ensure that path style access is used instead
              "enablePathStyleAccess": True
            },
            "objects": [
              {
                "bucket": "parquets",
                "path": "8090433b-b56d-40fb-af22-785c89848787/Test1.parquet"
              }
            ],
            "properties": {
               "accessKeyId": minio_access_key,
               "secretAccessKey": minio_secret_key
            }
          },
          "inputFormat": {
            "type": "parquet"
          }
        },
        "tuningConfig": {
          "type": "index_parallel",
          "partitionsSpec": {
            "type": "dynamic"
          }
        },
        "dataSchema": {
          "dataSource": "Test1",
          "timestampSpec": timestamp_spec,
          "dimensionsSpec": {
            "dimensions": schema
          },
          "granularitySpec": {
            "queryGranularity": "none",
            "rollup": False,
            "segmentGranularity": "day"
          }
        }
      }
    }
    task_logger.debug('Sending ingestion spec to Druid')
    client = requests.post(self.base_url, json = payload , auth=druid_auth)
    if not client.ok:
       task_logger.error('Sending of ingestion spec failed with code %d and message: “%s”', client.status_code, client.text)
       raise AirflowException('Failed to start Druid ingestion')
    task_logger.info('Ingestion spec sent to Druid. waiting for completion…')
    self.wait_for_completion(client.json()['task'])

  def wait_for_completion(self, process_id: str):
    self.defer(trigger=TimeDeltaTrigger(timedelta(seconds=5)), method_name="check_status", kwargs={ "process_id": process_id })

  def check_status(self, context: Context, event: Dict[str, Any], process_id: str , **kwargs):
    task_logger.debug('Checking status of Druid ingestion…')
    url = "{}/{}/status".format(self.base_url, process_id)
    response = requests.get(url, auth=druid_auth)
    if response.ok:
      status = response.json()['status']['statusCode']
      if status == 'FAILED':
          task_logger.error('Druid ingestion has failed!')
          raise AirflowException('Druid ingestion failed')
      elif status == 'SUCCESS':
          task_logger.info('Druid ingestion successfully completed')
          return
    task_logger.debug('Druid ingestion still running')
    self.wait_for_completion(process_id)

class SupersetOperator(BaseOperator):
  def __init__(self, **kwargs):
    super().__init__(task_id = 'link_dataset_to_superset', **kwargs)

  def execute(self, context: Context):
    client = SupersetClient(base_url = superset_base_url)
    db_id = self.prepare_db(client)

    # Fetch the current user ID
    superset_user_id = client.get_current_user_id('admin')

    dataset_id, explore_url = client.create_or_update_dataset(
            name='Test1', 
            db_name=db_id,
            owner_id=superset_user_id
        )
    self.xcom_push(context, 'superset_dataset_id', dataset_id)
    self.xcom_push(context, 'superset_dataset_url', explore_url)

  def prepare_db(self, client: SupersetClient) -> int:
    druid_url = urllib.parse.urlparse(druid_router_url)
    connection_str = "druid://admin:{}@{}/druid/v2/sql/".format(druid_admin_password, druid_url.netloc)
    db_id = client.ensure_db_exists(repan_db_name, connection_str)
    return db_id


with DAG("Test1", dag_display_name="Test1",default_args=default_args,start_date=datetime(2025, 7, 4), schedule_interval="@once", description="TEST", catchup=False, is_paused_upon_creation=False) as dag:

    task_logger.debug('Setting up components of DAG')

    # Download pipeline from minio bucket
    pipeline_minio = PythonOperator(
        task_id="pipeline_minio",
        python_callable=download_pipeline_minio
        )

    # Run Hop pipeline by sending it over HTTP to Hop server
    hop = HopPipelineOperator(
      task_id="test.hpl",
      task_display_name="test.hpl",
      pipeline="8090433b-b56d-40fb-af22-785c89848787/test.hpl",
      pipe_config='remote hop server',
      project_name='default',
      log_level='Basic',
      hop_params={'user_id':'8090433b-b56d-40fb-af22-785c89848787','minio_ftp':f'{minio_ftp}','dag_id':'Test1','dag_display_name':'Test1'}
    )

    # Run Druid ingestion
    druid = DruidOperator()

    superset = SupersetOperator()

    task_logger.debug('Now starting DAG…')

    pipeline_minio >> hop >> druid >> superset