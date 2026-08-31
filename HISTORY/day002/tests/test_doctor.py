import platform as host_platform
import shutil as host_shutil

import pytest

import airidl.doctor as doctor
from airidl.doctor import _version_at_least, collect_report, resolve_profile


def test_auto_profile_resolution() -> None:
    assert resolve_profile("auto", "Darwin") == "macos-dev"
    assert resolve_profile("auto", "Linux") == "portable-ci"
    assert (
        resolve_profile(
            "auto",
            "Linux",
            "x86_64",
            {"ID": "ubuntu", "VERSION_ID": "24.04"},
            "6.8.0-generic",
        )
        == "ubuntu-cuda"
    )
    assert resolve_profile("auto", "Linux", kernel_release="microsoft-wsl2") == "portable-ci"
    assert resolve_profile("portable-ci", "Darwin") == "portable-ci"


def test_version_comparison() -> None:
    assert _version_at_least("cmake version 4.3.3", (3, 28))
    assert _version_at_least("580.126.20", (580, 126, 20))
    assert not _version_at_least("release 12.9", (13, 0))


@pytest.mark.parametrize(
    ("driver", "expected_overall"),
    [("579.0.0", "fail"), ("580.126.20", "pass")],
)
def test_ubuntu_cuda_driver_gate(
    monkeypatch: pytest.MonkeyPatch, driver: str, expected_overall: str
) -> None:
    policy = doctor._load_policy()
    formal = policy["formal_target"]
    assert isinstance(formal, dict)
    monkeypatch.setattr(host_platform, "system", lambda: "Linux")
    monkeypatch.setattr(host_platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        host_platform,
        "freedesktop_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "24.04"},
    )
    monkeypatch.setattr(host_shutil, "which", lambda name: f"/fake/{name}")

    def fake_run(command: list[str]) -> str:
        joined = " ".join(command)
        if "driver_version" in joined:
            return driver
        if "compute_cap" in joined:
            return "NVIDIA RTX 5090, 12.0"
        if "nvcc" in joined:
            return "Cuda compilation tools, release 13.0, V13.0.88"
        return "13.3.0" if "g++" in joined else "4.3.3"

    monkeypatch.setattr(doctor, "_run", fake_run)
    report = collect_report("ubuntu-cuda")
    assert report["overall"] == expected_overall
    checks = report["checks"]
    assert isinstance(checks, list)
    driver_check = next(check for check in checks if check["name"] == "cuda_driver")
    assert driver_check["status"] == expected_overall


def test_command_with_nonzero_exit_is_missing() -> None:
    assert doctor._run(["/usr/bin/false"]) is None


def test_report_has_stable_contract() -> None:
    report = collect_report("portable-ci")
    assert report["schema"] == "airidl.doctor/v1"
    assert report["profile"] == "portable-ci"
    checks = report["checks"]
    assert isinstance(checks, list)
    assert [check["name"] for check in checks] == [
        "platform",
        "python",
        "cmake",
        "ninja",
        "c++",
        "cuda_driver",
        "cuda_toolkit",
        "gpu",
    ]
    assert {check["status"] for check in checks} <= {"pass", "warn", "fail", "skip"}
