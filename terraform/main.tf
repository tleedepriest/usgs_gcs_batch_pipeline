terraform {
  required_version = ">= 1.0"
  backend "local" {} # Can change from "local" to "gcs" (for google) or "s3" (for aws), if you would like to preserve your tf-state online
  required_providers {
    google = {
      source = "hashicorp/google"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "3.1.0"
    }
  }
}

provider "google" {
  project     = var.project
  region      = var.region
  credentials = file(var.credentials) # Use this if you do not want to set env-var GOOGLE_APPLICATION_CREDENTIALS
}

resource "google_project_service" "cloud_resource_manager" {
  service            = "cloudresourcemanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "compute" {
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}
# Data Lake Bucket
# Ref: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/storage_bucket
resource "google_storage_bucket" "data-lake-bucket" {
  name     = "${local.data_lake_bucket}_${var.project}" # Concatenating DL bucket & Project name for unique naming
  location = var.region

  # Optional, but recommended settings:
  storage_class               = var.storage_class
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 30 // days
    }
  }

  force_destroy = true
}

# DWH
# Ref: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/bigquery_dataset
resource "google_bigquery_dataset" "dataset" {
  dataset_id = var.BQ_DATASET
  project    = var.project
  location   = var.region
}

# https://binx.io/2022/01/07/how-to-create-a-vm-with-ssh-enabled-on-gcp/
provider "tls" {
  // no config needed
}

resource "tls_private_key" "ssh" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "local_file" "ssh_private_key_pem" {
  content         = tls_private_key.ssh.private_key_pem
  filename        = ".ssh/google_compute_engine"
  file_permission = "0600"
}

resource "google_compute_network" "vpc_network" {
  name = "my-network"
}

# create new service account for vm
resource "google_service_account" "default" {
  account_id   = var.vm_service_account_id
  display_name = "Service Account"
}

# Bootstrapping Script to Install Apache
data "template_file" "linux-metadata" {
  template = <<EOF
echo "-------------------------START SETUP---------------------------"
sudo apt-get -y update
sudo apt-get -y install \
ca-certificates \
curl \
gnupg \
lsb-release
sudo apt -y install unzip
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get -y update
sudo apt-get -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo chmod 666 /var/run/docker.sock
sudo apt install make
echo 'Clone git repo to EC2'
cd /home/ubuntu && git clone ${var.repo_url}
echo 'CD to ${var.repo_dir} directory'
cd ${var.repo_dir}
echo 'Start containers & Run db migrations'
make up
echo "-------------------------END SETUP---------------------------"
EOF
}

resource "google_compute_address" "static_ip" {
  name = "ubuntu-vm"
}

output "public_ip" {
  value = google_compute_address.static_ip.address
}

data "google_client_openid_userinfo" "me" {}

output "email"{
  value = data.google_client_openid_userinfo.me.email
}

resource "google_compute_instance" "default" {
  name         = "test"
  machine_type = "e2-medium"
  zone         = var.zone

  tags = ["airflow-instance"]
  
  metadata = {
    ssh-keys = "${split("@", data.google_client_openid_userinfo.me.email)[0]}:${tls_private_key.ssh.public_key_openssh}"
  }

  # https://gmusumeci.medium.com/how-to-deploy-an-ubuntu-linux-vm-instance-in-gcp-using-terraform-b94d0ed3a3a4
  
  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      labels = {
        my_label = "ubuntu-vm"
      }
    }
  }

  network_interface {
    network = google_compute_network.vpc_network.name

    access_config {
      #nat_ip = google_compute_address.static_ip.address
      // Ephemeral public IP
    }
  }


  metadata_startup_script = data.template_file.linux-metadata.rendered

  service_account {
    # Google recommends custom service accounts that have cloud-platform scope and permissions granted via IAM Roles.
    email  = google_service_account.default.email
    scopes = ["cloud-platform"]
  }
}

# https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_firewall

resource "google_compute_firewall" "inbound" {
  project       = var.project
  name          = "inbound-firewall-rule"
  network       = google_compute_network.vpc_network.name
  description   = "Creates firewall rule for inbound SCP"
  direction     = "INGRESS"
  source_ranges = ["0.0.0.0/0"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  target_tags = ["airflow-instance"]
}

resource "google_compute_firewall" "outbound" {
  project       = var.project
  name          = "outbound-firewall-rule"
  network       = google_compute_network.vpc_network.name
  description   = "Creates firewall rule for outbound Airflow 8080"
  direction     = "EGRESS"
  source_ranges = ["0.0.0.0/0"]

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }

  #allow {
  #  protocol = "-1"
  #  ports    = ["0"]
  #}

  target_tags = ["airflow-instance"]
}
