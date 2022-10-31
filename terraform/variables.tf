locals {
  data_lake_bucket = "usgs_data_lake"
}

variable "project" {
  description = "usgs-equake"
}

variable "region" {
  description = "Region for GCP resources. Choose as per your location: https://cloud.google.com/about/locations"
  default = "us-east4"
  type = string
}

variable "credentials" {
  description = "path to credentials file rather than setting env var."
  default = "~/.google/credentials/gcs_credentials_usgs_equake.json"
  type = string
}

variable "storage_class" {
  description = "Storage class type for your bucket. Check official docs for more info."
  default = "STANDARD"
}

variable "BQ_DATASET" {
  description = "BigQuery Dataset that raw data (from GCS) will be written to"
  type = string
  default = "equake_data"
}
