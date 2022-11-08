#utput "aws_region" {
# description = "Region set for AWS"
# value       = var.aws_region
#

output "vm_public_ip" {
  value = google_compute_address.static_ip.address
}

output "email"{
  value = data.google_client_openid_userinfo.me.email
}

#output "ec2_public_dns" {
#  description = "vm public dns."
#  value       = aws_instance.sde_ec2.public_dns
#}

output "private_key" {
  description = "vm private key."
  value       = tls_private_key.ssh.private_key_pem
  sensitive   = true
}

output "public_key" {
  description = "EC2 public key."
  value       = tls_private_key.ssh.public_key_openssh
}

output "vm_zone" {
  description = "zone of vm"
  value = var.zone

}
