provider "aws" {
  region                      = var.aws_region
  access_key                  = "mock"
  secret_key                  = "mock"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  
  # FIX 1: Forces S3 to use http://localhost:4566/bucket-name instead of bucket-name.localhost
  s3_use_path_style           = true

  endpoints {
    ec2 = "http://localhost:4566"
    s3  = "http://localhost:4566"
  }
}

module "network" {
  source      = "./modules/network"
  project     = "NimbusKart"
  environment = "staging"
}

# Security Group configuration
resource "aws_security_group" "web_sg" {
  name        = "nimbuskart-web-sg"
  vpc_id      = module.network.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  tags = {
    Project     = "NimbusKart"
    Environment = "staging"
    Owner       = "nimbuskart-devops"
    ManagedBy   = "terraform"
  }
}

# Mocking EC2 Web Tier
resource "aws_instance" "web_server" {
  count         = 2
  # FIX: Uses LocalStack's officially documented pre-seeded standard Linux AMI 
  ami           = "ami-df5de72bdb3b" 
  instance_type = "t3.micro"
  subnet_id     = module.network.subnet_ids[count.index]
  vpc_security_group_ids = [aws_security_group.web_sg.id]

  tags = {
    Name        = "NimbusKart-Web-Tier-${count.index}"
    Project     = "NimbusKart"
    Environment = "staging"
    Owner       = "nimbuskart-devops"
    ManagedBy   = "terraform"
  }
}



# Compliant S3 Bucket with Lifecycle Expiry rules
resource "aws_s3_bucket" "app_logs" {
  bucket = "nimbuskart-application-logs-staging"

  tags = {
    Project     = "NimbusKart"
    Environment = "staging"
    Owner       = "nimbuskart-devops"
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "logs_versioning" {
  bucket = aws_s3_bucket.app_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "logs_lifecycle" {
  bucket = aws_s3_bucket.app_logs.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# The known unattached orphan volume to be picked up by Part B Janitor
resource "aws_ebs_volume" "orphan_volume" {
  availability_zone = "us-east-1a"
  size              = 10

  tags = {
    Name        = "Orphaned-Data-Volume"
    Project     = "NimbusKart"
    Environment = "staging"
    Owner       = "nimbuskart-devops"
    ManagedBy   = "terraform"
  }
}
