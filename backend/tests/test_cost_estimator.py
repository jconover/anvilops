"""Unit tests for the CostEstimator service.

All tests exercise pure in-memory logic -- no database, Redis,
or external API connections are required.
"""

import pytest

from app.services.cost_estimator import CostEstimator


@pytest.fixture
def estimator() -> CostEstimator:
    return CostEstimator()


# ------------------------------------------------------------------
# Basic size / OS combinations
# ------------------------------------------------------------------


class TestEstimateBasicSizes:
    """Verify compute cost for each instance_size with a Linux OS."""

    def test_estimate_small_linux_default(self, estimator: CostEstimator):
        """small + amazon_linux_2023 in us-east-1 with no extra storage."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
        })
        assert result["instance_type"] == "t3.medium"
        assert result["instance_cost"] == 30.37  # 0.0416 * 730
        assert result["storage_cost"] == 2.40  # 30 GB gp3
        assert result["os_license_cost"] == 0.0
        assert result["total_monthly"] == 32.77
        assert result["currency"] == "USD"

    def test_estimate_medium_linux(self, estimator: CostEstimator):
        """medium + ubuntu_2204 -> t3.xlarge."""
        result = estimator.estimate({
            "instance_size": "medium",
            "os_type": "ubuntu_2204",
            "region": "us-east-1",
        })
        assert result["instance_type"] == "t3.xlarge"
        assert result["instance_cost"] == 121.47  # 0.1664 * 730
        assert result["storage_cost"] == 2.40
        assert result["total_monthly"] == 123.87

    def test_estimate_large_linux(self, estimator: CostEstimator):
        """large -> m5.2xlarge."""
        result = estimator.estimate({
            "instance_size": "large",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
        })
        assert result["instance_type"] == "m5.2xlarge"
        assert result["instance_cost"] == 280.32  # 0.384 * 730
        assert result["total_monthly"] == 282.72

    def test_estimate_xl_linux(self, estimator: CostEstimator):
        """xl -> m5.4xlarge."""
        result = estimator.estimate({
            "instance_size": "xl",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
        })
        assert result["instance_type"] == "m5.4xlarge"
        assert result["instance_cost"] == 560.64  # 0.768 * 730
        assert result["total_monthly"] == 563.04


# ------------------------------------------------------------------
# OS licence surcharges
# ------------------------------------------------------------------


class TestEstimateOSSurcharges:
    """Verify Windows and RHEL surcharges are applied correctly."""

    def test_estimate_windows_surcharge(self, estimator: CostEstimator):
        """small + windows_2022 -> Windows license + 100 GB root."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "windows_2022",
            "region": "us-east-1",
        })
        assert result["os_license_cost"] == 8.76  # 0.012 * 730
        assert result["storage_cost"] == 8.00  # 100 GB * 0.08
        assert result["instance_cost"] == 30.37
        assert result["total_monthly"] == 47.13

    def test_estimate_windows_2019(self, estimator: CostEstimator):
        """windows_2019 should also get the Windows surcharge + 100 GB root."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "windows_2019",
            "region": "us-east-1",
        })
        assert result["os_license_cost"] == 8.76
        assert result["storage_cost"] == 8.00
        assert result["total_monthly"] == 47.13

    def test_estimate_rhel_surcharge(self, estimator: CostEstimator):
        """small + rhel_9 -> RHEL hourly surcharge, 30 GB root."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "rhel_9",
            "region": "us-east-1",
        })
        assert result["os_license_cost"] == 43.80  # 0.06 * 730
        assert result["storage_cost"] == 2.40  # 30 GB * 0.08
        assert result["total_monthly"] == 76.57


# ------------------------------------------------------------------
# Region support
# ------------------------------------------------------------------


class TestEstimateRegions:
    def test_estimate_us_west_2(self, estimator: CostEstimator):
        """us-west-2 is a supported region with identical pricing."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-west-2",
        })
        assert result["instance_cost"] == 30.37
        assert result["total_monthly"] == 32.77


# ------------------------------------------------------------------
# Additional storage
# ------------------------------------------------------------------


class TestEstimateStorage:
    def test_estimate_with_gp3_storage(self, estimator: CostEstimator):
        """One additional 100 GB gp3 volume."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
            "additional_storage": [{"size_gb": 100, "volume_type": "gp3"}],
        })
        # Root: 30*0.08=2.4, additional: 100*0.08=8.0
        assert result["storage_cost"] == 10.40
        assert result["total_monthly"] == 40.77

    def test_estimate_with_io2_storage(self, estimator: CostEstimator):
        """One additional 200 GB io2 volume."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
            "additional_storage": [{"size_gb": 200, "volume_type": "io2"}],
        })
        # Root: 2.4, additional: 200*0.125=25.0
        assert result["storage_cost"] == 27.40
        assert result["total_monthly"] == 57.77

    def test_estimate_with_multiple_volumes(self, estimator: CostEstimator):
        """Two additional volumes -- costs are cumulative."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
            "additional_storage": [
                {"size_gb": 100, "volume_type": "gp3"},
                {"size_gb": 200, "volume_type": "io2"},
            ],
        })
        # Root: 2.4, gp3: 8.0, io2: 25.0 -> 35.4
        assert result["storage_cost"] == 35.40
        assert result["total_monthly"] == 65.77


# ------------------------------------------------------------------
# Annual cost
# ------------------------------------------------------------------


class TestEstimateAnnual:
    def test_estimate_annual_is_12x_monthly(self, estimator: CostEstimator):
        """total_annual must be exactly 12 * total_monthly."""
        result = estimator.estimate({
            "instance_size": "medium",
            "os_type": "windows_2022",
            "region": "us-east-1",
        })
        assert result["total_annual"] == round(result["total_monthly"] * 12, 2)


# ------------------------------------------------------------------
# Breakdown line items
# ------------------------------------------------------------------


class TestEstimateBreakdown:
    def test_estimate_breakdown_has_compute(self, estimator: CostEstimator):
        """Breakdown must contain a Compute entry."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
        })
        categories = [item["category"] for item in result["breakdown"]]
        assert "Compute" in categories

    def test_estimate_breakdown_has_storage(self, estimator: CostEstimator):
        """Breakdown must contain a Storage entry for the root volume."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
        })
        storage_items = [
            item for item in result["breakdown"] if item["category"] == "Storage"
        ]
        assert len(storage_items) >= 1
        # The root volume line should mention "Root volume"
        descriptions = [item["description"] for item in storage_items]
        assert any("Root volume" in d for d in descriptions)

    def test_estimate_breakdown_windows_license(self, estimator: CostEstimator):
        """Windows OS should produce a License breakdown with 'Windows Server License'."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "windows_2022",
            "region": "us-east-1",
        })
        license_items = [
            item for item in result["breakdown"] if item["category"] == "License"
        ]
        assert len(license_items) == 1
        assert "Windows Server License" in license_items[0]["description"]

    def test_estimate_breakdown_rhel_license(self, estimator: CostEstimator):
        """RHEL should produce a License breakdown with 'RHEL Subscription'."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "rhel_9",
            "region": "us-east-1",
        })
        license_items = [
            item for item in result["breakdown"] if item["category"] == "License"
        ]
        assert len(license_items) == 1
        assert "RHEL Subscription" in license_items[0]["description"]

    def test_estimate_breakdown_additional_storage(self, estimator: CostEstimator):
        """Extra volumes appear in breakdown with 'Additional EBS'."""
        result = estimator.estimate({
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
            "additional_storage": [{"size_gb": 50, "volume_type": "gp3"}],
        })
        additional = [
            item
            for item in result["breakdown"]
            if "Additional EBS" in item["description"]
        ]
        assert len(additional) == 1
        assert additional[0]["monthly_cost"] == 4.00  # 50 * 0.08


# ------------------------------------------------------------------
# Validation / error handling
# ------------------------------------------------------------------


class TestEstimateValidation:
    def test_estimate_invalid_size_raises(self, estimator: CostEstimator):
        """Unsupported instance_size should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported instance_size"):
            estimator.estimate({
                "instance_size": "micro",
                "os_type": "amazon_linux_2023",
                "region": "us-east-1",
            })

    def test_estimate_invalid_region_raises(self, estimator: CostEstimator):
        """Unsupported region should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported region"):
            estimator.estimate({
                "instance_size": "small",
                "os_type": "amazon_linux_2023",
                "region": "eu-west-1",
            })


# ------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------


class TestEstimateDefaults:
    def test_estimate_defaults(self, estimator: CostEstimator):
        """Empty config should default to small / amazon_linux_2023 / us-east-1."""
        result = estimator.estimate({})
        assert result["instance_type"] == "t3.medium"
        assert result["instance_cost"] == 30.37
        assert result["storage_cost"] == 2.40
        assert result["os_license_cost"] == 0.0
        assert result["total_monthly"] == 32.77


# ------------------------------------------------------------------
# get_pricing_table
# ------------------------------------------------------------------


class TestPricingTable:
    def test_pricing_table_structure(self, estimator: CostEstimator):
        """get_pricing_table returns all expected top-level keys."""
        table = estimator.get_pricing_table()
        expected_keys = {
            "regions",
            "sizes",
            "ebs",
            "windows_surcharge",
            "rhel_surcharge_hourly",
            "rhel_surcharge_monthly",
            "root_volumes",
            "hours_per_month",
            "instance_specs",
            "currency",
        }
        assert set(table.keys()) == expected_keys

    def test_pricing_table_has_both_regions(self, estimator: CostEstimator):
        """Pricing table must list us-east-1 and us-west-2."""
        table = estimator.get_pricing_table()
        assert "us-east-1" in table["regions"]
        assert "us-west-2" in table["regions"]
