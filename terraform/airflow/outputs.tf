output "jammy_vm_address" {
  value      = google_compute_instance.jammy_vm.network_interface[0].network_ip
}
