terraform {
  backend "s3" {
    bucket         = "anvilops-terraform-state"
    key            = "servers/terraform.tfstate"
    region         = "us-east-1"
    use_lockfile   = true
    encrypt        = true

    # Staging uses the same state bucket with workspace isolation.
    # Workspace names are prefixed by the API: stg-SERVERNAME
  }
}
