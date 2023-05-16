variable "machine" {
  type = string
}

variable "zone" {
  type = string
}

variable "image" {
  type        = string
  description = "OS system image of the VMs"
}

variable "vpc_network_name" {
  type = string
}

variable "jammy_vm_address" {
  type = string
}
