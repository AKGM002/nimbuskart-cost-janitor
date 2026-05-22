resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true

  tags = {
    Name        = "${var.project}-${var.environment}-vpc"
    Project     = var.project
    Environment = var.environment
    Owner       = "nimbuskart-devops"
    ManagedBy   = "terraform"
  }
}

resource "aws_subnet" "public_1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.20.1.0/24"
  availability_zone = "us-east-1a"

  tags = {
    Name        = "${var.project}-${var.environment}-public-1"
    Project     = var.project
    Environment = var.environment
    Owner       = "nimbuskart-devops"
    ManagedBy   = "terraform"
  }
}

resource "aws_subnet" "public_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.20.2.0/24"
  availability_zone = "us-east-1b"

  tags = {
    Name        = "${var.project}-${var.environment}-public-2"
    Project     = var.project
    Environment = var.environment
    Owner       = "nimbuskart-devops"
    ManagedBy   = "terraform"
  }
}
