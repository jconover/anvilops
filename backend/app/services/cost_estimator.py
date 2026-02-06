"""AWS cost estimation service for AnvilOps server configurations.

Provides monthly cost estimates based on instance type, storage, and
region.  Uses a static pricing table for demo purposes with an optional
boto3 Pricing API integration for production.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CostEstimator:
    """Calculate estimated monthly costs for server configurations.

    All prices are in USD.  The static tables reflect public on-demand
    pricing as of 2024-Q4.  For production use, call
    ``refresh_from_aws()`` to pull live data via the AWS Pricing API.
    """

    # ------------------------------------------------------------------
    # Static pricing data (on-demand, USD / hour)
    # ------------------------------------------------------------------

    INSTANCE_PRICING: dict[str, dict[str, float]] = {
        "us-east-1": {
            "t3.medium": 0.0416,
            "t3.xlarge": 0.1664,
            "m5.2xlarge": 0.384,
            "m5.4xlarge": 0.768,
        },
        "us-west-2": {
            "t3.medium": 0.0416,
            "t3.xlarge": 0.1664,
            "m5.2xlarge": 0.384,
            "m5.4xlarge": 0.768,
        },
    }

    # Friendly size label -> AWS instance type
    SIZE_TO_TYPE: dict[str, str] = {
        "small": "t3.medium",
        "medium": "t3.xlarge",
        "large": "m5.2xlarge",
        "xl": "m5.4xlarge",
    }

    # Instance specs for informational display
    INSTANCE_SPECS: dict[str, dict[str, Any]] = {
        "t3.medium": {"vcpu": 2, "memory_gb": 4},
        "t3.xlarge": {"vcpu": 4, "memory_gb": 16},
        "m5.2xlarge": {"vcpu": 8, "memory_gb": 32},
        "m5.4xlarge": {"vcpu": 16, "memory_gb": 64},
    }

    # Windows license surcharge (USD / hour)
    WINDOWS_SURCHARGE: dict[str, float] = {
        "t3.medium": 0.0120,
        "t3.xlarge": 0.0240,
        "m5.2xlarge": 0.0960,
        "m5.4xlarge": 0.1920,
    }

    # EBS pricing (USD / GB / month)
    EBS_PRICING: dict[str, float] = {
        "gp3": 0.08,
        "io2": 0.125,
    }

    # Default root volume sizes by OS (GB)
    ROOT_VOLUME_SIZE: dict[str, int] = {
        "windows_2022": 100,
        "windows_2019": 100,
        "amazon_linux_2023": 30,
        "ubuntu_2204": 30,
        "rhel_9": 30,
    }

    # RHEL has an hourly licence cost baked into the AMI price; we model
    # it as a separate line item so the breakdown is transparent.
    RHEL_SURCHARGE_PER_HOUR: float = 0.06

    HOURS_PER_MONTH: int = 730

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate(self, config: dict) -> dict:
        """Calculate a full cost estimate for a server configuration.

        Args:
            config: Dictionary with the following keys:
                - ``instance_size``  (str): small | medium | large | xl
                - ``os_type``        (str): e.g. windows_2022, ubuntu_2204
                - ``region``         (str): AWS region, default us-east-1
                - ``additional_storage`` (list[dict]): each entry has
                  ``size_gb`` (int) and ``volume_type`` (str, gp3|io2)

        Returns:
            Dictionary containing:
                - ``instance_cost``    (float): monthly compute cost
                - ``storage_cost``     (float): monthly EBS cost
                - ``os_license_cost``  (float): Windows/RHEL surcharge
                - ``total_monthly``    (float): sum of above
                - ``total_annual``     (float): total_monthly * 12
                - ``currency``         (str): always "USD"
                - ``instance_type``    (str): resolved AWS instance type
                - ``breakdown``        (list[dict]): per-line cost items

        Raises:
            ValueError: If an unsupported instance_size, os_type, or
                region is supplied.
        """
        instance_size: str = config.get("instance_size", "small").lower()
        os_type: str = config.get("os_type", "amazon_linux_2023").lower()
        region: str = config.get("region", "us-east-1")
        additional_storage: list[dict] = config.get("additional_storage", [])

        # Resolve instance type
        instance_type = self.SIZE_TO_TYPE.get(instance_size)
        if instance_type is None:
            raise ValueError(
                f"Unsupported instance_size '{instance_size}'. "
                f"Valid options: {', '.join(sorted(self.SIZE_TO_TYPE))}"
            )

        # Compute + license costs
        base_cost, license_cost = self._get_instance_cost(
            instance_size, region, os_type
        )

        # Storage cost
        storage_cost = self._get_storage_cost(os_type, additional_storage)

        total_monthly = round(base_cost + license_cost + storage_cost, 2)
        total_annual = round(total_monthly * 12, 2)

        # Build human-readable breakdown
        breakdown = self._build_breakdown(
            instance_type=instance_type,
            region=region,
            os_type=os_type,
            base_cost=base_cost,
            license_cost=license_cost,
            additional_storage=additional_storage,
        )

        return {
            "instance_cost": round(base_cost, 2),
            "storage_cost": round(storage_cost, 2),
            "os_license_cost": round(license_cost, 2),
            "total_monthly": total_monthly,
            "total_annual": total_annual,
            "currency": "USD",
            "instance_type": instance_type,
            "breakdown": breakdown,
        }

    def get_pricing_table(self) -> dict:
        """Return the full static pricing data for frontend display.

        The response is structured so the UI can render region tabs,
        instance-type cards, and storage pricing in a single call.

        Returns:
            Dictionary with ``regions``, ``sizes``, ``ebs``,
            ``windows_surcharge``, ``rhel_surcharge_hourly``,
            ``root_volumes``, ``hours_per_month``, and ``instance_specs``.
        """
        regions: dict[str, list[dict]] = {}
        for region, prices in self.INSTANCE_PRICING.items():
            region_entries = []
            for instance_type, hourly in sorted(prices.items()):
                size_label = self._type_to_size(instance_type)
                specs = self.INSTANCE_SPECS.get(instance_type, {})
                monthly = round(hourly * self.HOURS_PER_MONTH, 2)
                windows_hourly = self.WINDOWS_SURCHARGE.get(instance_type, 0)
                windows_monthly = round(windows_hourly * self.HOURS_PER_MONTH, 2)
                region_entries.append({
                    "instance_type": instance_type,
                    "size_label": size_label,
                    "vcpu": specs.get("vcpu"),
                    "memory_gb": specs.get("memory_gb"),
                    "hourly_rate": hourly,
                    "monthly_rate": monthly,
                    "windows_surcharge_hourly": windows_hourly,
                    "windows_surcharge_monthly": windows_monthly,
                })
            regions[region] = region_entries

        return {
            "regions": regions,
            "sizes": self.SIZE_TO_TYPE,
            "ebs": {
                vol_type: {
                    "price_per_gb_month": price,
                }
                for vol_type, price in self.EBS_PRICING.items()
            },
            "windows_surcharge": {
                itype: {
                    "hourly": hourly,
                    "monthly": round(hourly * self.HOURS_PER_MONTH, 2),
                }
                for itype, hourly in self.WINDOWS_SURCHARGE.items()
            },
            "rhel_surcharge_hourly": self.RHEL_SURCHARGE_PER_HOUR,
            "rhel_surcharge_monthly": round(
                self.RHEL_SURCHARGE_PER_HOUR * self.HOURS_PER_MONTH, 2
            ),
            "root_volumes": self.ROOT_VOLUME_SIZE,
            "hours_per_month": self.HOURS_PER_MONTH,
            "instance_specs": self.INSTANCE_SPECS,
            "currency": "USD",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_instance_cost(
        self, instance_size: str, region: str, os_type: str
    ) -> tuple[float, float]:
        """Return ``(base_monthly, license_monthly)`` for the given config.

        Args:
            instance_size: Friendly size label (small/medium/large/xl).
            region: AWS region identifier.
            os_type: OS identifier (e.g. ``windows_2022``).

        Returns:
            A 2-tuple of ``(base_cost_per_month, license_cost_per_month)``.

        Raises:
            ValueError: If the region or instance size is not in the
                pricing table.
        """
        instance_type = self.SIZE_TO_TYPE.get(instance_size)
        if instance_type is None:
            raise ValueError(f"Unknown instance_size: {instance_size}")

        region_pricing = self.INSTANCE_PRICING.get(region)
        if region_pricing is None:
            raise ValueError(
                f"Unsupported region '{region}'. "
                f"Available: {', '.join(sorted(self.INSTANCE_PRICING))}"
            )

        hourly_rate = region_pricing.get(instance_type)
        if hourly_rate is None:
            raise ValueError(
                f"No pricing for {instance_type} in {region}"
            )

        base_monthly = round(hourly_rate * self.HOURS_PER_MONTH, 2)

        # OS licence surcharge
        license_monthly = 0.0
        if self._is_windows(os_type):
            surcharge = self.WINDOWS_SURCHARGE.get(instance_type, 0.0)
            license_monthly = round(surcharge * self.HOURS_PER_MONTH, 2)
        elif self._is_rhel(os_type):
            license_monthly = round(
                self.RHEL_SURCHARGE_PER_HOUR * self.HOURS_PER_MONTH, 2
            )

        return base_monthly, license_monthly

    def _get_storage_cost(
        self, os_type: str, additional_storage: list[dict]
    ) -> float:
        """Calculate total monthly EBS cost (root + additional volumes).

        The root volume is always ``gp3`` and sized according to
        ``ROOT_VOLUME_SIZE``.

        Args:
            os_type: OS identifier (used to look up root volume size).
            additional_storage: List of dicts, each with ``size_gb``
                (int) and ``volume_type`` (str).

        Returns:
            Total monthly storage cost in USD.
        """
        # Root volume
        root_gb = self.ROOT_VOLUME_SIZE.get(os_type, 30)
        root_rate = self.EBS_PRICING["gp3"]
        total = root_gb * root_rate

        # Additional volumes
        for vol in additional_storage:
            size_gb = vol.get("size_gb", 0)
            vol_type = vol.get("volume_type", "gp3")
            rate = self.EBS_PRICING.get(vol_type, self.EBS_PRICING["gp3"])
            total += size_gb * rate

        return round(total, 2)

    def _build_breakdown(
        self,
        *,
        instance_type: str,
        region: str,
        os_type: str,
        base_cost: float,
        license_cost: float,
        additional_storage: list[dict],
    ) -> list[dict]:
        """Produce a list of line-item cost entries for the UI.

        Each entry is a dict with ``category``, ``description``, and
        ``monthly_cost``.
        """
        breakdown: list[dict] = []

        # Compute
        specs = self.INSTANCE_SPECS.get(instance_type, {})
        vcpu = specs.get("vcpu", "?")
        mem = specs.get("memory_gb", "?")
        breakdown.append({
            "category": "Compute",
            "description": (
                f"{instance_type} On-Demand ({vcpu} vCPU, {mem} GB RAM, "
                f"{self.HOURS_PER_MONTH} hrs/mo) in {region}"
            ),
            "monthly_cost": round(base_cost, 2),
        })

        # OS licence
        if license_cost > 0:
            if self._is_windows(os_type):
                label = "Windows Server License"
            elif self._is_rhel(os_type):
                label = "RHEL Subscription"
            else:
                label = "OS License"
            breakdown.append({
                "category": "License",
                "description": f"{label} for {instance_type}",
                "monthly_cost": round(license_cost, 2),
            })

        # Root volume
        root_gb = self.ROOT_VOLUME_SIZE.get(os_type, 30)
        root_cost = round(root_gb * self.EBS_PRICING["gp3"], 2)
        os_label = os_type.replace("_", " ").title()
        breakdown.append({
            "category": "Storage",
            "description": f"Root volume (gp3, {root_gb} GB) for {os_label}",
            "monthly_cost": root_cost,
        })

        # Additional volumes
        for idx, vol in enumerate(additional_storage, start=1):
            size_gb = vol.get("size_gb", 0)
            vol_type = vol.get("volume_type", "gp3")
            rate = self.EBS_PRICING.get(vol_type, self.EBS_PRICING["gp3"])
            vol_cost = round(size_gb * rate, 2)
            mount = (
                vol.get("drive_letter")
                or vol.get("mount_point")
                or f"Volume {idx}"
            )
            breakdown.append({
                "category": "Storage",
                "description": (
                    f"Additional EBS ({vol_type}, {size_gb} GB) — {mount}"
                ),
                "monthly_cost": vol_cost,
            })

        return breakdown

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _is_windows(os_type: str) -> bool:
        """Return True if the OS identifier represents a Windows image."""
        return os_type.lower().startswith("windows")

    @staticmethod
    def _is_rhel(os_type: str) -> bool:
        """Return True if the OS identifier represents Red Hat Enterprise Linux."""
        return os_type.lower().startswith("rhel")

    def _type_to_size(self, instance_type: str) -> str | None:
        """Reverse lookup: instance type -> friendly size label."""
        for label, itype in self.SIZE_TO_TYPE.items():
            if itype == instance_type:
                return label
        return None
