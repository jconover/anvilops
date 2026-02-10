output "cluster_name" {
  description = "Name of the EKS cluster."
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  description = "Endpoint URL for the EKS cluster API server."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_ca_certificate" {
  description = "Base64-encoded certificate authority data for the EKS cluster."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_version" {
  description = "Kubernetes version running on the EKS cluster."
  value       = aws_eks_cluster.this.version
}

output "cluster_security_group_id" {
  description = "Cluster security group created by EKS."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "oidc_provider_arn" {
  description = "ARN of the OIDC provider for IRSA."
  value       = aws_iam_openid_connect_provider.eks.arn
}

output "oidc_provider_url" {
  description = "OIDC provider URL without https:// prefix, for IAM trust policy conditions."
  value       = replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")
}

output "node_group_role_arn" {
  description = "ARN of the IAM role assigned to the managed node group."
  value       = aws_iam_role.node_group.arn
}

output "cluster_role_arn" {
  description = "ARN of the IAM role assigned to the EKS cluster control plane."
  value       = aws_iam_role.cluster.arn
}
