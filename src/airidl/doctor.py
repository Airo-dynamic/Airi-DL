"""Read-only host capability inspection for the current learning snapshot."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal, cast

from airidl import __version__

Status = Literal["pass", "warn", "fail", "skip"]
Profile = Literal["auto", "macos-dev", "portable-ci", "ubuntu-cuda"]


@dataclass(frozen=True)
class Check:
    name: str
    required: bool
    status: Status
    expected: str
    actual: str | None


def resolve_profile(
    requested: Profile,
    system: str | None = None,
    machine: str | None = None,
    os_release: dict[str, str] | None = None,
    kernel_release: str | None = None,
) -> str:
    if requested != "auto":
        return requested
    host_system = system or platform.system()
    if host_system == "Darwin":
        return "macos-dev"
    if host_system != "Linux":
        return "portable-ci"
    release = kernel_release or platform.release()
    if "microsoft" in release.lower():
        return "portable-ci"
    distro = os_release
    if distro is None:
        try:
            distro = platform.freedesktop_os_release()
        except OSError:
            distro = {}
    host_machine = machine or platform.machine()
    if (
        distro.get("ID") == "ubuntu"
        and distro.get("VERSION_ID", "").startswith("24.04")
        and host_machine in {"x86_64", "AMD64"}
    ):
        return "ubuntu-cuda"
    return "portable-ci"


def _run(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, check=False, text=True, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    output = (result.stdout or result.stderr).strip()
    return output if output else None


def _version_at_least(actual: str, minimum: tuple[int, ...]) -> bool:
    match = re.search(r"\d+(?:\.\d+)+", actual)
    if match is None:
        return False
    found = tuple(int(part) for part in match.group().split("."))
    padded = found + (0,) * max(0, len(minimum) - len(found))
    return padded[: len(minimum)] >= minimum


def _tool(
    name: str,
    expected: str,
    required: bool,
    minimum: tuple[int, ...] | None = None,
    executable: str | None = None,
) -> Check:
    path = shutil.which(executable or name)
    if path is None:
        return Check(name, required, "fail" if required else "skip", expected, None)
    output = _run([path, "--version"])
    actual = output.splitlines()[0] if output else path.rsplit("/", 1)[-1]
    ok = minimum is None or _version_at_least(actual, minimum)
    return Check(name, required, "pass" if ok else "fail", expected, actual)


def _platform_check(profile: str, formal: dict[str, object]) -> Check:
    system, machine = platform.system(), platform.machine()
    actual = f"{system} {machine}"
    if profile == "macos-dev":
        ok, expected = system == "Darwin", "Darwin (CPU development)"
    elif profile == "ubuntu-cuda":
        try:
            os_release = platform.freedesktop_os_release()
        except OSError:
            os_release = {}
        actual = f"{os_release.get('ID', system)} {os_release.get('VERSION_ID', '')} {machine}"
        ok = (
            os_release.get("ID") == "ubuntu"
            and os_release.get("VERSION_ID", "").startswith("24.04")
            and machine in {"x86_64", "AMD64"}
        )
        expected = f"{formal['os']} {formal['architecture']}"
    else:
        ok, expected = system in {"Darwin", "Linux"}, "Darwin or Linux"
    return Check("platform", True, "pass" if ok else "fail", expected, actual)


def _python_check(formal: dict[str, object]) -> Check:
    actual = platform.python_version()
    expected = str(formal["python"])
    major, minor = (int(part) for part in expected.split("."))
    ok = sys.version_info[:2] == (major, minor)
    return Check("python", True, "pass" if ok else "fail", f"{expected}.x", actual)


def _cuda_checks(required: bool, formal: dict[str, object]) -> list[Check]:
    driver_min = str(formal["cuda_driver_min"])
    toolkit_series = str(formal["cuda_series"])
    if not required:
        return [
            Check("cuda_driver", False, "skip", f">={driver_min}", None),
            Check("cuda_toolkit", False, "skip", f"{toolkit_series}.x", None),
            Check("gpu", False, "skip", "compute capability 12.0", None),
        ]

    smi, nvcc = shutil.which("nvidia-smi"), shutil.which("nvcc")
    driver = _run([smi, "--query-gpu=driver_version", "--format=csv,noheader"]) if smi else None
    toolkit = _run([nvcc, "--version"]) if nvcc else None
    gpu = _run([smi, "--query-gpu=name,compute_cap", "--format=csv,noheader"]) if smi else None
    driver_floor = tuple(int(part) for part in driver_min.split("."))
    driver_ok = driver is not None and all(
        _version_at_least(line, driver_floor) for line in driver.splitlines()
    )
    toolkit_ok = toolkit is not None and f"release {toolkit_series}" in toolkit
    gpu_ok = gpu is not None and "12.0" in gpu
    return [
        Check("cuda_driver", True, "pass" if driver_ok else "fail", f">={driver_min}", driver),
        Check(
            "cuda_toolkit", True, "pass" if toolkit_ok else "fail", f"{toolkit_series}.x", toolkit
        ),
        Check("gpu", True, "pass" if gpu_ok else "fail", "compute capability 12.0", gpu),
    ]


def _load_policy() -> dict[str, object]:
    source_path = Path(__file__).resolve().parents[2] / "env" / "versions.toml"
    if source_path.is_file():
        with source_path.open("rb") as stream:
            return cast(dict[str, object], tomllib.load(stream))
    with files("airidl").joinpath("versions.toml").open("rb") as stream:
        return cast(dict[str, object], tomllib.load(stream))


def collect_report(requested: Profile = "auto") -> dict[str, object]:
    policy = _load_policy()
    formal = cast(dict[str, object], policy["formal_target"])
    project = cast(dict[str, object], policy["project"])
    profile = resolve_profile(requested)
    checks = [
        _platform_check(profile, formal),
        _python_check(formal),
        _tool(
            "cmake",
            f">={formal['cmake_min']}",
            True,
            tuple(int(part) for part in str(formal["cmake_min"]).split(".")),
        ),
        _tool(
            "ninja",
            f">={formal['ninja_min']}",
            True,
            tuple(int(part) for part in str(formal["ninja_min"]).split(".")),
        ),
        _tool(
            "c++",
            "GCC 13 / C++20" if profile == "ubuntu-cuda" else "C++20 compiler",
            True,
            (13, 3) if profile == "ubuntu-cuda" else None,
            "g++-13" if profile == "ubuntu-cuda" else "c++",
        ),
        *_cuda_checks(profile == "ubuntu-cuda", formal),
    ]
    overall = "fail" if any(c.required and c.status == "fail" for c in checks) else "pass"
    return {
        "schema": "airidl.doctor/v1",
        "project": {
            "name": project["name"],
            "snapshot": project["snapshot"],
            "version": __version__,
        },
        "requested_profile": requested,
        "profile": profile,
        "overall": overall,
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "capabilities": {
            "cpp": all(c.status == "pass" for c in checks if c.name in {"cmake", "ninja", "c++"}),
            "cuda": all(
                c.status == "pass" for c in checks if c.name.startswith("cuda") or c.name == "gpu"
            ),
        },
        "checks": [asdict(check) for check in checks],
    }
