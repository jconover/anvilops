# AnvilOps site manifest
#
# Primary node classification is handled by Puppet Enterprise Console (ENC).
# This file provides fallback classification for nodes not assigned via Console.
#
# The ENC assigns roles based on server metadata passed during provisioning.
# If a node reaches this manifest, it gets the base role at minimum.

node default {
  # All nodes get the base role at minimum
  # This ensures monitoring, security baselines, and patching are enforced
  include role::base
}
