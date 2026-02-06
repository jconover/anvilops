locals {
  volumes_map = { for idx, vol in var.volumes : vol.device_name => vol }
}

resource "aws_ebs_volume" "this" {
  for_each = local.volumes_map

  availability_zone = var.availability_zone
  size              = each.value.size_gb
  type              = each.value.volume_type
  encrypted         = true

  tags = merge(
    {
      Name      = "anvilops-${each.key}"
      ManagedBy = "AnvilOps"
      Device    = each.key
    },
    var.tags,
    each.value.tags
  )
}

resource "aws_volume_attachment" "this" {
  for_each = local.volumes_map

  device_name = each.key
  volume_id   = aws_ebs_volume.this[each.key].id
  instance_id = var.instance_id

  # Prevent forced detachment which could cause data loss
  force_detach = false
}
