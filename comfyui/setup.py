#!/usr/bin/env python3
"""
ComfyUI Declarative Setup Script

Reads comfyui.yaml and sets up ComfyUI with custom nodes and models.
"""

import argparse
import hashlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("PyYAML not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
    import yaml


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"


def info(msg: str) -> None:
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")


def success(msg: str) -> None:
    print(f"{Colors.GREEN}[OK]{Colors.NC} {msg}")


def warn(msg: str) -> None:
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {msg}")


def error(msg: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}")


def run_cmd(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def git_clone(url: str, dest: Path, branch: str | None = None, depth: int = 1) -> bool:
    """Clone a git repository."""
    cmd = ["git", "clone", "--depth", str(depth)]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([url, str(dest)])
    try:
        run_cmd(cmd)
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to clone {url}: {e.stderr}")
        return False


def git_checkout(repo_path: Path, rev: str) -> bool:
    """Checkout a specific revision."""
    try:
        run_cmd(["git", "fetch", "--all", "--tags"], cwd=repo_path)
        run_cmd(["git", "checkout", rev], cwd=repo_path)
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to checkout {rev}: {e.stderr}")
        return False


def git_current_version(repo_path: Path) -> str | None:
    """Get the current git tag or commit."""
    try:
        result = run_cmd(["git", "describe", "--tags"], cwd=repo_path, check=False)
        if result.returncode == 0:
            return result.stdout.strip()
        result = run_cmd(["git", "rev-parse", "--short", "HEAD"], cwd=repo_path)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def download_file(url: str, dest: Path, expected_sha256: str | None = None) -> bool:
    """Download a file with resume support and optional hash verification."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Use wget for resume support
        cmd = ["wget", "-c", "-q", "--show-progress", "-O", str(dest), url]
        subprocess.run(cmd, check=True)
        
        if expected_sha256:
            info(f"Verifying checksum for {dest.name}...")
            sha256 = hashlib.sha256()
            with open(dest, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            if sha256.hexdigest() != expected_sha256:
                error(f"Checksum mismatch for {dest.name}")
                dest.unlink()
                return False
        
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to download {url}")
        if dest.exists():
            dest.unlink()
        return False


def setup_comfyui(config: dict[str, Any], base_dir: Path) -> bool:
    """Clone or update ComfyUI."""
    comfyui_config = config.get("comfyui", {})
    version = comfyui_config.get("version", "latest")
    repo = comfyui_config.get("repo", "https://github.com/comfyanonymous/ComfyUI")
    install_dir = base_dir / comfyui_config.get("install_dir", "ComfyUI")
    
    info("Checking ComfyUI installation...")
    
    if not install_dir.exists():
        info(f"Cloning ComfyUI v{version}...")
        branch = f"v{version}" if version != "latest" else None
        if git_clone(repo, install_dir, branch=branch):
            success(f"ComfyUI v{version} cloned successfully")
            return True
        return False
    
    current = git_current_version(install_dir)
    expected = f"v{version}"
    
    if current != expected and version != "latest":
        warn(f"Current version: {current}, expected: {expected}")
        info(f"Updating to {expected}...")
        if git_checkout(install_dir, expected):
            success(f"ComfyUI updated to {expected}")
        else:
            return False
    else:
        success(f"ComfyUI {current} already installed")
    
    return True


def setup_custom_nodes(config: dict[str, Any], base_dir: Path) -> bool:
    """Install custom nodes."""
    comfyui_dir = base_dir / config.get("comfyui", {}).get("install_dir", "ComfyUI")
    custom_nodes_dir = comfyui_dir / "custom_nodes"
    custom_nodes_dir.mkdir(parents=True, exist_ok=True)
    
    nodes = config.get("custom_nodes", {})
    if not nodes:
        info("No custom nodes configured")
        return True
    
    all_success = True
    for name, node_config in nodes.items():
        info(f"Checking custom node: {name}...")
        node_dir = custom_nodes_dir / name
        url = node_config.get("url")
        rev = node_config.get("rev", "main")
        
        if not url:
            error(f"No URL specified for {name}")
            all_success = False
            continue
        
        if not node_dir.exists():
            info(f"Cloning {name}...")
            if git_clone(url, node_dir):
                if git_checkout(node_dir, rev):
                    success(f"{name} installed at {rev}")
                else:
                    all_success = False
            else:
                all_success = False
        else:
            current = git_current_version(node_dir)
            if current != rev:
                info(f"Updating {name} to {rev}...")
                if git_checkout(node_dir, rev):
                    success(f"{name} updated to {rev}")
                else:
                    all_success = False
            else:
                success(f"{name} already at {rev}")
        
        # Install requirements.txt if present
        requirements_file = node_dir / "requirements.txt"
        if requirements_file.exists():
            info(f"Installing requirements for {name}...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements_file)],
                    check=True,
                    capture_output=True
                )
            except subprocess.CalledProcessError:
                warn(f"Some requirements for {name} failed (may be optional)")
        
        # Install additional pip dependencies
        pip_deps = node_config.get("pip_deps", [])
        if pip_deps:
            info(f"Installing pip dependencies for {name}...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q"] + pip_deps,
                    check=True,
                    capture_output=True
                )
            except subprocess.CalledProcessError as e:
                warn(f"Some pip deps for {name} failed: {e}")
    
    return all_success


def download_model(args: tuple[str, str, dict, Path]) -> tuple[str, bool]:
    """Download a single model (for parallel execution)."""
    model_type, name, model_config, models_dir = args
    url = model_config.get("url")
    sha256 = model_config.get("sha256")
    dest = models_dir / model_type / name
    
    if dest.exists():
        success(f"Model exists: {model_type}/{name}")
        return (name, True)
    
    info(f"Downloading {model_type}/{name}...")
    if download_file(url, dest, sha256):
        success(f"Downloaded: {model_type}/{name}")
        return (name, True)
    return (name, False)


def setup_models(config: dict[str, Any], base_dir: Path, include_optional: bool = False, parallel: int = 2) -> bool:
    """Download models."""
    comfyui_dir = base_dir / config.get("comfyui", {}).get("install_dir", "ComfyUI")
    models_dir = comfyui_dir / "models"
    
    models = config.get("models", {})
    if not models:
        info("No models configured")
        return True
    
    download_tasks = []
    for model_type, type_models in models.items():
        if not isinstance(type_models, dict):
            continue
        for name, model_config in type_models.items():
            if not isinstance(model_config, dict):
                continue
            
            optional = model_config.get("optional", False)
            if optional and not include_optional:
                info(f"Skipping optional model: {model_type}/{name}")
                continue
            
            download_tasks.append((model_type, name, model_config, models_dir))
    
    if not download_tasks:
        info("No models to download")
        return True
    
    all_success = True
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(download_model, task): task for task in download_tasks}
        for future in as_completed(futures):
            name, ok = future.result()
            if not ok:
                all_success = False
    
    return all_success


def setup_pip_packages(config: dict[str, Any]) -> bool:
    """Install additional pip packages."""
    packages = config.get("pip_packages", [])
    if not packages:
        return True
    
    info(f"Installing pip packages: {', '.join(packages)}")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q"] + packages,
            check=True,
            capture_output=True
        )
        success("Pip packages installed")
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to install pip packages: {e.stderr}")
        return False


def main():
    parser = argparse.ArgumentParser(description="ComfyUI Declarative Setup")
    parser.add_argument("--config", "-c", default="comfyui.yaml", help="Path to config file")
    parser.add_argument("--all", "-a", action="store_true", help="Include optional models")
    parser.add_argument("--parallel", "-p", type=int, default=2, help="Parallel model downloads")
    parser.add_argument("--skip-models", action="store_true", help="Skip model downloads")
    parser.add_argument("--skip-nodes", action="store_true", help="Skip custom nodes")
    parser.add_argument("--skip-pip", action="store_true", help="Skip pip packages")
    args = parser.parse_args()
    
    # Determine base directory
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    
    base_dir = config_path.parent
    
    if not config_path.exists():
        error(f"Config file not found: {config_path}")
        sys.exit(1)
    
    # Load config
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    print()
    print("=" * 44)
    print("  ComfyUI Declarative Setup")
    print("=" * 44)
    print()
    
    # Run setup steps
    if not setup_comfyui(config, base_dir):
        error("ComfyUI setup failed")
        sys.exit(1)
    
    if not args.skip_pip:
        if not setup_pip_packages(config):
            warn("Some pip packages failed to install")
    
    if not args.skip_nodes:
        if not setup_custom_nodes(config, base_dir):
            warn("Some custom nodes failed to install")
    
    if not args.skip_models:
        if not setup_models(config, base_dir, include_optional=args.all, parallel=args.parallel):
            warn("Some models failed to download")
    
    print()
    success("Setup complete!")
    print()
    
    install_dir = base_dir / config.get("comfyui", {}).get("install_dir", "ComfyUI")
    print(f"To start ComfyUI:")
    print(f"  cd {install_dir} && python main.py --listen 0.0.0.0 --port 8188")
    print()


if __name__ == "__main__":
    main()
