variable "vpc_cidr" {
  type        = string
  default     = "10.20.0.0/16"
}

variable "environment" {
  type        = string
}

variable "project" {
  type        = string
}
