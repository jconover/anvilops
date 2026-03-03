terraform {
  backend "s3" {
    bucket       = "anvilops-terraform-state"
    key          = "servers/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true

    # Each server gets its own workspace, so the actual key becomes:
    # env:/WORKSPACE_NAME/servers/terraform.tfstate
    # The API creates a workspace per server for maximum isolation.
  }
}
