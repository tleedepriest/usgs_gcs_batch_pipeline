locals {
  data_lake_bucket = "usgs_data_lake"
}

variable "project" {
  default     = "usgs-equake"
  description = "The project id"
}

variable "vm_service_account_id" {
  default     = "vm-usgs-equake-user"
  description = "service account id assigned to vm"

}

variable "region" {
  description = "Region for GCP resources. Choose as per your location: https://cloud.google.com/about/locations"
  default     = "us-east4"
  type        = string
}

variable "zone" {
  description = ""
  default     = "us-central1-a"
  type        = string
}

variable "credentials" {
  description = "path to credentials file rather than setting env var."
  default     = "~/.google/credentials/gcs_credentials_usgs_equake.json"
  type        = string
}

variable "storage_class" {
  description = "Storage class type for your bucket. Check official docs for more info."
  default     = "STANDARD"
}

variable "BQ_DATASET" {
  description = "BigQuery Dataset that raw data (from GCS) will be written to"
  type        = string
  default     = "equake_data"
}

## Your repository url
variable "repo_url" {
  description = "Repository url to clone into production machine"
  type        = string
  default     = "https://github.com/tleedepriest/usgs_gcs_batch_pipeline.git"
}

variable "repo_dir" {
  description = "main directory for repo"
  type        = string
  default     = "usgs_gcs_batch_pipeline"
}
