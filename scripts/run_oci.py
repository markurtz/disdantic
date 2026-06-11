"""
A unified platform-agnostic OCI runner script.

This module provides CLI commands to run various OCI linting, testing, and auditing
tools (such as hadolint, dclint, dockle, trivy, and container-structure-test)
either locally or via fallback Docker containers.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import sys
from collections.abc import Generator
from os import environ
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

__all__ = [
    "IMAGE_NAME",
    "SETTINGS_FILE_NAME",
    "TAR_FILE",
    "app",
    "check_image_exists",
    "cmd_compose_config",
    "cmd_cstest",
    "cmd_dclint",
    "cmd_dockle",
    "cmd_hadolint",
    "cmd_trivy",
    "is_docker_running",
    "main",
]

IMAGE_NAME: Annotated[
    str,
    "The name of the OCI image to target for scanning, building, or auditing.",
] = environ.get("OCI_IMAGE", "disdantic:latest")

SETTINGS_FILE_NAME: Annotated[
    str,
    "The settings file name to accept/suppress from Dockle checks.",
] = "settings.py"

TAR_FILE: Annotated[
    Path,
    "The path to the temporary image tarball used by auditing tools.",
] = Path("disdantic.tar")

app: Annotated[
    typer.Typer,
    "The Typer CLI application instance for executing OCI tasks.",
] = typer.Typer(
    help="Unified platform-agnostic OCI runner.",
    no_args_is_help=True,
    add_completion=False,
)


def is_docker_running() -> bool:
    """
    Check if the Docker daemon is available and running.

    Example:
        >>> is_docker_running()
        True

    :return: True if the Docker daemon is responsive, False otherwise.
    """
    try:
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def check_image_exists(image: str) -> bool:
    """
    Check if the specified Docker image exists locally.

    Example:
        >>> check_image_exists("disdantic:latest")
        True

    :param image: The name or tag of the Docker image.
    :return: True if the image exists, False otherwise.
    """
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except subprocess.SubprocessError:
        return False


def run_hadolint(extra_args: list[str]) -> None:
    """
    Run Hadolint linter on Dockerfile.

    If Hadolint is installed locally, it runs it directly. Otherwise, it falls
    back to running Hadolint within a Docker container.

    Example:
        >>> run_hadolint(["--ignore", "DL3006"])

    :param extra_args: Additional command line arguments passed to Hadolint.
    :raises SystemExit: If the linter command returns a non-zero exit code.
    """
    dockerfile = Path("Dockerfile")
    if not dockerfile.exists():
        logger.warning(f"No {dockerfile} found. Skipping hadolint.")
        return

    option_flags = {
        "-c",
        "--config",
        "--ignore",
        "--trusted-registry",
        "-f",
        "--format",
    }
    args = _add_default_positional(extra_args, str(dockerfile), option_flags)

    # Check if hadolint is installed locally
    local_path = shutil.which("hadolint")
    if local_path:
        logger.info(f"Running local hadolint with args {args}...")
        res = subprocess.run([local_path] + args, check=False)
        if res.returncode != 0:
            sys.exit(res.returncode)
        return

    # Fallback to Docker
    if not is_docker_running():
        logger.warning(
            "hadolint is not installed locally and Docker is not running. "
            f"Skipping hadolint with args {args}."
        )
        return

    logger.info(f"Running hadolint via Docker with args {args}...")
    try:
        pwd = Path.cwd()
        res = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{pwd}:/app",
                "-w",
                "/app",
                "hadolint/hadolint",
                "/bin/hadolint",
            ]
            + args,
            check=False,
        )
        if res.returncode != 0:
            sys.exit(res.returncode)
    except subprocess.SubprocessError as error:
        logger.error(f"Failed to run hadolint via Docker: {error}")
        sys.exit(1)


def run_dclint(extra_args: list[str]) -> None:
    """
    Run dclint on compose files.

    If dclint is installed locally, it runs it directly. Otherwise, it falls
    back to running dclint within a Docker container.

    Example:
        >>> run_dclint(["-f", "docker-compose.yml"])

    :param extra_args: Additional command line arguments passed to dclint.
    :raises SystemExit: If the linter command returns a non-zero exit code.
    """
    option_flags = {
        "-f",
        "--formatter",
        "-c",
        "--config",
        "-o",
        "--output-file",
        "--max-warnings",
        "-e",
        "--exclude",
        "--disable-rule",
    }
    args = _add_default_positional(extra_args, ".", option_flags)

    local_path = shutil.which("dclint")
    if local_path:
        logger.info(f"Running local dclint with args {args}...")
        res = subprocess.run([local_path] + args, check=False)
        if res.returncode != 0:
            sys.exit(res.returncode)
        return

    # Fallback to Docker
    if not is_docker_running():
        logger.warning(
            "dclint is not installed locally and Docker is not running. "
            f"Skipping dclint with args {args}."
        )
        return

    logger.info(f"Running dclint via Docker with args {args}...")
    try:
        pwd = Path.cwd()
        res = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{pwd}:/app",
                "-w",
                "/app",
                "zavoloklom/dclint",
            ]
            + args,
            check=False,
        )
        if res.returncode != 0:
            sys.exit(res.returncode)
    except subprocess.SubprocessError as error:
        logger.error(f"Failed to run dclint via Docker: {error}")
        sys.exit(1)


def run_compose_config(extra_args: list[str]) -> None:
    """
    Validate docker compose configuration.

    Runs the `docker compose config` command to check compose files.

    Example:
        >>> run_compose_config(["config", "-q"])

    :param extra_args: Additional command line arguments passed to docker compose.
    :raises SystemExit: If the validation command returns a non-zero exit code.
    """
    if not is_docker_running():
        logger.warning(
            "Docker is not running. Skipping docker compose config check "
            f"with args {extra_args}."
        )
        return

    logger.info(f"Checking docker compose config with args {extra_args}...")
    args = extra_args if extra_args else ["config", "-q"]
    res = subprocess.run(["docker", "compose"] + args, check=False)
    if res.returncode != 0:
        sys.exit(res.returncode)


def run_dockle(extra_args: list[str]) -> None:
    """
    Run Dockle container audit.

    If Dockle is installed locally, it runs it directly. Otherwise, it falls
    back to exporting the image to a tarball and running Dockle via Docker.

    Example:
        >>> run_dockle([])

    :param extra_args: Additional command line arguments passed to Dockle.
    :raises SystemExit: If the audit command returns a non-zero exit code.
    """
    local_path = shutil.which("dockle")
    if local_path:
        option_flags = {
            "-c",
            "--config",
            "-f",
            "--format",
            "-o",
            "--output",
            "-i",
            "--input",
            "--accept-key",
            "--ignore",
            "--accept-file",
            "-af",
        }
        args = extra_args.copy()
        if not any(arg in args for arg in ["--accept-file", "-af"]):
            args.extend(["--accept-file", SETTINGS_FILE_NAME])
        args = _add_default_positional(args, IMAGE_NAME, option_flags)
        logger.info(f"Running local dockle with args {args}...")
        res = subprocess.run([local_path] + args, check=False)
        if res.returncode != 0:
            sys.exit(res.returncode)
        return

    # Fallback to Docker
    if not is_docker_running():
        logger.warning(
            "dockle is not installed locally and Docker is not running. "
            f"Skipping dockle audit with args {extra_args}."
        )
        return

    logger.info(
        f"Running dockle via Docker against exported tarball with args {extra_args}..."
    )
    try:
        with _temp_image_tar(IMAGE_NAME, TAR_FILE):
            pwd = Path.cwd()
            args = extra_args.copy()
            if not any(arg in args for arg in ["--input", "-i"]):
                args.extend(["--input", str(TAR_FILE)])
            if not any(arg in args for arg in ["--accept-file", "-af"]):
                args.extend(["--accept-file", SETTINGS_FILE_NAME])

            res = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{pwd}:/app",
                    "-w",
                    "/app",
                    "goodwithtech/dockle:latest",
                ]
                + args,
                check=False,
            )
            if res.returncode != 0:
                sys.exit(res.returncode)
    except subprocess.SubprocessError as error:
        logger.error(f"Failed to run dockle audit: {error}")
        sys.exit(1)


def run_trivy(extra_args: list[str]) -> None:
    """
    Run Trivy security scan.

    If Trivy is installed locally, it runs it directly. Otherwise, it falls
    back to exporting the image to a tarball and running Trivy via Docker.

    Example:
        >>> run_trivy(["--severity", "HIGH,CRITICAL"])

    :param extra_args: Additional command line arguments passed to Trivy.
    :raises SystemExit: If the security scan returns a non-zero exit code.
    """
    local_path = shutil.which("trivy")
    if local_path:
        args = extra_args.copy()
        if not any(
            arg in args for arg in ["image", "fs", "repo", "config", "rootfs", "sbom"]
        ):
            args.insert(0, "image")

        if args[0] == "image":
            option_flags = {
                "-f",
                "--format",
                "-o",
                "--output",
                "-s",
                "--severity",
                "-c",
                "--config",
                "--vuln-type",
                "--security-checks",
                "--ignore-policy",
                "--ignorefile",
                "--cache-dir",
            }
            sub_args = _add_default_positional(args[1:], IMAGE_NAME, option_flags)
            args = [args[0]] + sub_args

        logger.info(f"Running local trivy with args {args}...")
        res = subprocess.run([local_path] + args, check=False)
        if res.returncode != 0:
            sys.exit(res.returncode)
        return

    # Fallback to Docker
    if not is_docker_running():
        logger.warning(
            "trivy is not installed locally and Docker is not running. "
            f"Skipping trivy scan with args {extra_args}."
        )
        return

    logger.info(
        f"Running trivy via Docker against exported tarball with args {extra_args}..."
    )
    try:
        with _temp_image_tar(IMAGE_NAME, TAR_FILE):
            pwd = Path.cwd()
            cache_dir = Path(pwd) / ".trivycache"
            cache_dir.mkdir(exist_ok=True)

            args = extra_args.copy()
            if not any(
                arg in args
                for arg in ["image", "fs", "repo", "config", "rootfs", "sbom"]
            ):
                args.insert(0, "image")
            if not any(arg in args for arg in ["--input", "-i"]):
                args.extend(["--input", str(TAR_FILE)])

            res = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{pwd}:/app",
                    "-v",
                    f"{cache_dir}:/root/.cache",
                    "-w",
                    "/app",
                    "aquasec/trivy:latest",
                ]
                + args,
                check=False,
            )
            if res.returncode != 0:
                sys.exit(res.returncode)
    except subprocess.SubprocessError as error:
        logger.error(f"Failed to run trivy scan: {error}")
        sys.exit(1)


def run_cstest(extra_args: list[str]) -> None:
    """
    Run Container Structure Test (cstest).

    If container-structure-test is installed locally, it runs it directly.
    Otherwise, it runs container-structure-test via Docker with docker.sock mounted.

    Example:
        >>> run_cstest([])

    :param extra_args: Additional command line arguments passed to cstest.
    :raises SystemExit: If the test command returns a non-zero exit code.
    """
    local_path = shutil.which("container-structure-test")
    if local_path:
        logger.info(f"Running local container-structure-test with args {extra_args}...")
        args = _build_cstest_args(extra_args, "cst.yaml")
        res = subprocess.run([local_path] + args, check=False)
        if res.returncode != 0:
            sys.exit(res.returncode)
        return

    # Fallback to Docker
    if not is_docker_running():
        logger.warning(
            "container-structure-test is not installed locally and "
            f"Docker is not running. Skipping cstest with args {extra_args}."
        )
        return

    if not check_image_exists(IMAGE_NAME):
        logger.info(f"Image {IMAGE_NAME} not found. Building it first...")
        subprocess.run(["docker", "build", "-t", IMAGE_NAME, "."], check=True)

    logger.info(
        f"Running container-structure-test via Docker with args {extra_args}..."
    )
    try:
        pwd = Path.cwd()
        args = _build_cstest_args(extra_args, "/etc/cstest/cst.yaml")
        res = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{pwd}:/etc/cstest:ro",
                "-v",
                "/var/run/docker.sock:/var/run/docker.sock:ro",
                "ghcr.io/googlecontainertools/container-structure-test:latest",
            ]
            + args,
            check=False,
        )
        if res.returncode != 0:
            sys.exit(res.returncode)
    except subprocess.SubprocessError as error:
        logger.error(f"Failed to run container-structure-test: {error}")
        sys.exit(1)


@app.command(
    "hadolint",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
def cmd_hadolint(ctx: typer.Context) -> None:
    """
    Run Hadolint linter on Dockerfile via the CLI.

    Example:
        $ python run_oci.py hadolint --ignore DL3006

    :param ctx: The Typer context containing extra command line arguments.
    """
    run_hadolint(ctx.args)


@app.command(
    "dclint",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
def cmd_dclint(ctx: typer.Context) -> None:
    """
    Run dclint on compose files via the CLI.

    Example:
        $ python run_oci.py dclint .

    :param ctx: The Typer context containing extra command line arguments.
    """
    run_dclint(ctx.args)


@app.command(
    "compose-config",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
def cmd_compose_config(ctx: typer.Context) -> None:
    """
    Validate docker compose configuration via the CLI.

    Example:
        $ python run_oci.py compose-config

    :param ctx: The Typer context containing extra command line arguments.
    """
    run_compose_config(ctx.args)


@app.command(
    "dockle",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
def cmd_dockle(ctx: typer.Context) -> None:
    """
    Run Dockle container audit via the CLI.

    Example:
        $ python run_oci.py dockle

    :param ctx: The Typer context containing extra command line arguments.
    """
    run_dockle(ctx.args)


@app.command(
    "trivy",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
def cmd_trivy(ctx: typer.Context) -> None:
    """
    Run Trivy security scan via the CLI.

    Example:
        $ python run_oci.py trivy --severity HIGH,CRITICAL

    :param ctx: The Typer context containing extra command line arguments.
    """
    run_trivy(ctx.args)


@app.command(
    "cstest",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
def cmd_cstest(ctx: typer.Context) -> None:
    """
    Run Container Structure Test (cstest) via the CLI.

    Example:
        $ python run_oci.py cstest --config cst.yaml

    :param ctx: The Typer context containing extra command line arguments.
    """
    run_cstest(ctx.args)


@contextlib.contextmanager
def _temp_image_tar(image: str, tar_path: Path) -> Generator[None, None, None]:
    """Save the Docker image to a tarball and ensure it is cleaned up."""
    if not check_image_exists(image):
        logger.error(
            f"Image {image} not found. Build it first (e.g. hatch run oci:build)."
        )
        sys.exit(1)

    logger.info(f"Saving image {image} to {tar_path}...")
    subprocess.run(["docker", "save", image, "-o", str(tar_path)], check=True)
    try:
        yield
    finally:
        if tar_path.exists():
            tar_path.unlink()


def _add_default_positional(
    args: list[str], default_val: str, option_flags: set[str]
) -> list[str]:
    """
    Append a default positional argument to the args list if none is present
    and no help or version flags are requested.

    :param args: List of command line arguments.
    :param default_val: The default positional argument to append.
    :param option_flags: Set of option flags that take a parameter.
    :return: The list of arguments, possibly with default_val appended.
    """
    # Check for help/version flags first
    if any(flag in args for flag in ["--help", "-h", "--version", "-v"]):
        return args

    # Check for existing positional arguments
    has_positional = False
    skip_next = False
    for argument in args:
        if skip_next:
            skip_next = False
            continue
        if argument.startswith("-"):
            if argument in option_flags:
                skip_next = True
        else:
            has_positional = True
            break

    if not has_positional:
        return args + [default_val]
    return args


def _build_cstest_args(extra_args: list[str], default_config: str) -> list[str]:
    """Build args for container-structure-test."""
    args = extra_args.copy()
    if "test" not in args:
        args.insert(0, "test")
    if not any(arg in args for arg in ["--image", "-i"]):
        args.extend(["--image", IMAGE_NAME])
    if not any(arg in args for arg in ["--config", "-c"]):
        args.extend(["--config", default_config])
    return args


def main() -> None:
    """
    Main execution entrypoint to run the Typer CLI application.

    Example:
        >>> main()
    """
    app()


if __name__ == "__main__":
    main()
