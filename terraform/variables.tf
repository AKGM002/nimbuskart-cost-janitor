variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "ssh_allowed_cidr" {
  type        = string
  default     = "0.0.0.0/0" # Setting a default, but we MUST document the risk in README!
}
