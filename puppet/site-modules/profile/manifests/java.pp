# @summary Java runtime environment profile for Linux
#
# This profile installs and configures a Java Development Kit (JDK) on Linux
# systems. It supports Amazon Corretto (recommended for AWS workloads) and
# manages JAVA_HOME environment variables.
#
# @param version
#   Java version to install (e.g., '8', '11', '17', '21')
# @param vendor
#   Java vendor/distribution (currently supports 'corretto' and 'openjdk')
# @param set_default
#   Whether to set this Java version as the system default
#
# @example Basic usage (installs latest LTS)
#   include profile::java
#
# @example Install specific version
#   class { 'profile::java':
#     version => '17',
#     vendor  => 'corretto',
#   }
#
class profile::java (
  String $version = '21',
  Enum['corretto', 'openjdk'] $vendor = 'corretto',
  Boolean $set_default = true,
) {
  # Fail fast if not Linux
  if $facts['os']['family'] !~ /^(RedHat|Debian)$/ {
    fail("profile::java can only be applied to Linux systems, not ${facts['os']['family']}")
  }

  case $vendor {
    'corretto': {
      case $facts['os']['family'] {
        'RedHat': {
          # Amazon Corretto repository for RHEL/CentOS/Amazon Linux
          exec { 'import-corretto-key':
            command => '/usr/bin/rpm --import https://yum.corretto.aws/corretto.key',
            unless  => '/usr/bin/rpm -q gpg-pubkey --qf "%{summary}\n" | /usr/bin/grep -q "Corretto"',
          }

          yumrepo { 'corretto':
            descr    => "Amazon Corretto ${version}",
            baseurl  => "https://yum.corretto.aws/corretto-${version}/\$basearch/",
            enabled  => 1,
            gpgcheck => 1,
            gpgkey   => 'https://yum.corretto.aws/corretto.key',
            require  => Exec['import-corretto-key'],
          }

          $package_name = "java-${version}-amazon-corretto-devel"

          package { $package_name:
            ensure  => installed,
            require => Yumrepo['corretto'],
          }

          $java_home = "/usr/lib/jvm/java-${version}-amazon-corretto"
        }
        'Debian': {
          # Amazon Corretto repository for Debian/Ubuntu
          ensure_packages(['apt-transport-https', 'ca-certificates', 'wget', 'software-properties-common'], {
            'ensure' => 'installed',
          })

          exec { 'import-corretto-key-ubuntu':
            command => '/usr/bin/wget -qO - https://apt.corretto.aws/corretto.key | /usr/bin/apt-key add -',
            unless  => '/usr/bin/apt-key list | /usr/bin/grep -q "Corretto"',
            require => Package['wget'],
          }

          exec { 'add-corretto-repo':
            command => "/usr/bin/add-apt-repository 'deb https://apt.corretto.aws stable main'",
            unless  => '/usr/bin/test -f /etc/apt/sources.list.d/corretto.list',
            require => [Package['software-properties-common'], Exec['import-corretto-key-ubuntu']],
          }

          exec { 'apt-update-corretto':
            command     => '/usr/bin/apt-get update',
            refreshonly => true,
            subscribe   => Exec['add-corretto-repo'],
          }

          $package_name = "java-${version}-amazon-corretto-jdk"

          package { $package_name:
            ensure  => installed,
            require => Exec['apt-update-corretto'],
          }

          $java_home = "/usr/lib/jvm/java-${version}-amazon-corretto"
        }
        default: {
          fail("Unsupported OS family for Corretto: ${facts['os']['family']}")
        }
      }
    }
    'openjdk': {
      case $facts['os']['family'] {
        'RedHat': {
          $package_name = "java-${version}-openjdk-devel"

          package { $package_name:
            ensure => installed,
          }

          $java_home = "/usr/lib/jvm/java-${version}-openjdk"
        }
        'Debian': {
          $package_name = "openjdk-${version}-jdk"

          package { $package_name:
            ensure => installed,
          }

          $java_home = "/usr/lib/jvm/java-${version}-openjdk-amd64"
        }
        default: {
          fail("Unsupported OS family for OpenJDK: ${facts['os']['family']}")
        }
      }
    }
    default: {
      fail("Unsupported Java vendor: ${vendor}")
    }
  }

  # Set JAVA_HOME in system profile
  file { '/etc/profile.d/java.sh':
    ensure  => file,
    content => epp('profile/java_profile.sh.epp', {
      'java_home' => $java_home,
    }),
    mode    => '0644',
    require => Package[$package_name],
  }

  # Set alternatives if multiple Java versions exist
  if $set_default {
    case $facts['os']['family'] {
      'RedHat': {
        exec { 'set-java-alternative':
          command => "/usr/sbin/alternatives --set java ${java_home}/bin/java",
          unless  => "/usr/sbin/alternatives --display java | /usr/bin/grep -q 'link currently points to ${java_home}/bin/java'",
          require => Package[$package_name],
        }

        exec { 'set-javac-alternative':
          command => "/usr/sbin/alternatives --set javac ${java_home}/bin/javac",
          unless  => "/usr/sbin/alternatives --display javac | /usr/bin/grep -q 'link currently points to ${java_home}/bin/javac'",
          require => Package[$package_name],
        }
      }
      'Debian': {
        exec { 'set-java-alternative':
          command => "/usr/bin/update-alternatives --set java ${java_home}/bin/java",
          unless  => "/usr/bin/update-alternatives --query java | /usr/bin/grep -q 'Value: ${java_home}/bin/java'",
          require => Package[$package_name],
        }

        exec { 'set-javac-alternative':
          command => "/usr/bin/update-alternatives --set javac ${java_home}/bin/javac",
          unless  => "/usr/bin/update-alternatives --query javac | /usr/bin/grep -q 'Value: ${java_home}/bin/javac'",
          require => Package[$package_name],
        }
      }
      default: {
        # Do nothing
      }
    }
  }

  # Verify Java installation
  exec { 'verify-java-installation':
    command => "${java_home}/bin/java -version",
    unless  => "${java_home}/bin/java -version 2>&1 | /usr/bin/grep -q 'version \"${version}'",
    require => Package[$package_name],
  }
}
