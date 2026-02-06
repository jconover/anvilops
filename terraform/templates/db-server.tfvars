# =============================================================================
# Template: SQL Server Standard
# =============================================================================
# Windows Server 2022, Large (8 vCPU/32GB), SQL Server 2022 Standard
# 500GB io2 data drive, 200GB io2 log drive, 100GB gp3 tempdb drive
# AD-joined, database security profile
# =============================================================================

os_type          = "windows_2022"
instance_size    = "large"
security_profile = "database"
domain_join      = true
puppet_role      = "db_server"
root_volume_size = 100

additional_storage = [
  {
    device_name = "xvdf"
    size_gb     = 500
    volume_type = "io2"
    tags = {
      Purpose = "SQL-Data"
      Drive   = "D"
    }
  },
  {
    device_name = "xvdg"
    size_gb     = 200
    volume_type = "io2"
    tags = {
      Purpose = "SQL-Logs"
      Drive   = "E"
    }
  },
  {
    device_name = "xvdh"
    size_gb     = 100
    volume_type = "gp3"
    tags = {
      Purpose = "SQL-TempDB"
      Drive   = "F"
    }
  }
]

tags = {
  Template = "sql-server"
  Role     = "database"
}
