#!/usr/bin/env python3
"""
ComfyUI Declarative Model Sync Script
Downloads and installs models defined in models.yaml
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import yaml


def get_workspace() -> Path:
    """Get the ComfyUI workspace directory."""
    workspace = os.environ.get("COMFYUI_WORKSPACE")
    if workspace:
        return Path(workspace)
    return Path.cwd()


def get_models_dir() -> Path:
    """Get the models directory."""
    return get_workspace() / "ComfyUI" / "models"


def get_token(token_type: str) -> Optional[str]:
    """Get API token from secrets file."""
    token_paths = {
        "huggingface": "/run/secrets/hugging_face_api_key",
        "civitai": "/run/secrets/civitai_api_key",
    }
    path = token_paths.get(token_type)
    if path and os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    env_vars = {
        "huggingface": "HF_TOKEN",
        "civitai": "CIVITAI_API_TOKEN",
    }
    return os.environ.get(env_vars.get(token_type, ""))


def download_huggingface(model: dict, dest_dir: Path) -> bool:
    """Download a model from HuggingFace."""
    repo = model["repo"]
    filename = model.get("file")
    subfolder = model.get("subfolder", "")
    token = get_token("huggingface")

    dest_dir.mkdir(parents=True, exist_ok=True)

    if filename:
        # Single file download
        dest_file = dest_dir / filename
        if dest_file.exists():
            print(f"  [SKIP] Already exists: {dest_file.name}")
            return True

        url = f"https://huggingface.co/{repo}/resolve/main/"
        if subfolder:
            url += f"{subfolder}/"
        url += filename

        cmd = ["wget", "-q", "--show-progress", "-O", str(dest_file), url]
        if token:
            cmd.insert(2, f"--header=Authorization: Bearer {token}")

        print(f"  [DOWNLOAD] {filename} from {repo}")
        result = subprocess.run(cmd)
        return result.returncode == 0
    else:
        # Clone entire repo or subfolder using git-lfs
        repo_name = repo.split("/")[-1]
        dest_path = dest_dir / repo_name
        
        if dest_path.exists():
            print(f"  [SKIP] Already exists: {repo_name}")
            return True

        clone_url = f"https://huggingface.co/{repo}"
        if token:
            clone_url = f"https://USER:{token}@huggingface.co/{repo}"

        print(f"  [CLONE] {repo}")
        env = os.environ.copy()
        env["GIT_LFS_SKIP_SMUDGE"] = "0"  # Enable LFS
        
        cmd = ["git", "clone", "--depth", "1", clone_url, str(dest_path)]
        result = subprocess.run(cmd, env=env)
        
        if result.returncode == 0 and subfolder:
            # If subfolder specified, we could optionally clean up other folders
            pass
        
        return result.returncode == 0


def download_civitai(model: dict, dest_dir: Path) -> bool:
    """Download a model from CivitAI."""
    model_id = model.get("model_id")
    version_id = model.get("version_id")
    token = get_token("civitai")

    dest_dir.mkdir(parents=True, exist_ok=True)

    # CivitAI API endpoint
    if version_id:
        url = f"https://civitai.com/api/download/models/{version_id}"
    else:
        url = f"https://civitai.com/api/download/models/{model_id}"

    if token:
        url += f"?token={token}"

    # Get filename from headers or use model name
    filename = model.get("filename", f"{model['name']}.safetensors")
    dest_file = dest_dir / filename

    if dest_file.exists():
        print(f"  [SKIP] Already exists: {filename}")
        return True

    print(f"  [DOWNLOAD] {filename} from CivitAI (model: {model_id})")
    cmd = ["wget", "-q", "--show-progress", "--content-disposition", "-O", str(dest_file), url]
    result = subprocess.run(cmd)
    return result.returncode == 0


def download_github(model: dict, dest_dir: Path) -> bool:
    """Download from GitHub releases."""
    repo = model["repo"]
    release = model.get("release", "latest")
    asset = model["asset"]
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / asset

    if dest_file.exists():
        print(f"  [SKIP] Already exists: {asset}")
        return True

    if release == "latest":
        url = f"https://github.com/{repo}/releases/latest/download/{asset}"
    else:
        url = f"https://github.com/{repo}/releases/download/{release}/{asset}"

    print(f"  [DOWNLOAD] {asset} from {repo}")
    cmd = ["wget", "-q", "--show-progress", "-O", str(dest_file), url]
    result = subprocess.run(cmd)
    return result.returncode == 0


def download_git(model: dict, dest_dir: Path, use_path_directly: bool = False) -> bool:
    """Clone a git repository."""
    repo_url = model["repo"]
    repo_name = model.get("name", repo_url.rstrip("/").split("/")[-1])
    
    # If use_path_directly is True, clone directly into dest_dir (don't append repo_name)
    if use_path_directly:
        dest_path = dest_dir
    else:
        dest_path = dest_dir / repo_name
    
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.exists() and any(dest_path.iterdir()):
        print(f"  [SKIP] Already exists: {dest_path.name}")
        return True

    # Check if it's a HuggingFace repo and add token
    token = None
    if "huggingface.co" in repo_url:
        token = get_token("huggingface")
        if token and "@" not in repo_url:
            # Insert token into URL
            repo_url = repo_url.replace("https://", f"https://USER:{token}@")

    print(f"  [CLONE] {repo_name} -> {dest_path}")
    env = os.environ.copy()
    
    # Clone with LFS enabled
    cmd = ["git", "clone", "--depth", "1", repo_url, str(dest_path)]
    result = subprocess.run(cmd, env=env)
    
    if result.returncode != 0:
        return False
    
    # Pull LFS files if present
    gitattributes = dest_path / ".gitattributes"
    if gitattributes.exists() and "lfs" in gitattributes.read_text():
        print(f"  [LFS] Fetching large files...")
        lfs_result = subprocess.run(
            ["git", "lfs", "pull", "--include=*"],
            cwd=str(dest_path)
        )
        if lfs_result.returncode != 0:
            print(f"  [WARN] LFS pull failed, some files may be incomplete")
    
    return True


def download_url(model: dict, dest_dir: Path) -> bool:
    """Download from direct URL."""
    url = model["url"]
    filename = model.get("filename", url.split("/")[-1].split("?")[0])
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / filename

    if dest_file.exists():
        print(f"  [SKIP] Already exists: {filename}")
        return True

    print(f"  [DOWNLOAD] {filename}")
    cmd = ["wget", "-q", "--show-progress", "-O", str(dest_file), url]
    result = subprocess.run(cmd)
    return result.returncode == 0


def sync_models(config_path: Path, dry_run: bool = False, model_filter: Optional[str] = None, tag_filter: Optional[str] = None) -> int:
    """Sync all models from config file."""
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        return 1

    with open(config_path) as f:
        config = yaml.safe_load(f)

    models = config.get("models", [])
    if not models:
        print("No models defined in config.")
        return 0

    models_dir = get_models_dir()
    print(f"Models directory: {models_dir}")
    print(f"Config file: {config_path}")
    
    # Filter by tag if specified
    if tag_filter:
        tag_filter_lower = tag_filter.lower()
        models = [m for m in models if any(tag_filter_lower == t.lower() for t in m.get("tags", []))]
        print(f"Filtering by tag: {tag_filter}")
    
    print(f"Found {len(models)} model(s) to sync\n")

    success_count = 0
    fail_count = 0
    skip_count = 0

    handlers = {
        "huggingface": download_huggingface,
        "civitai": download_civitai,
        "github": download_github,
        "git": download_git,
        "url": download_url,
    }

    for model in models:
        name = model.get("name", "unnamed")
        
        if model_filter and model_filter.lower() not in name.lower():
            continue
            
        model_type = model.get("type", "checkpoints")
        source = model.get("source", "url")
        tags = model.get("tags", [])
        # Custom path overrides the default type-based destination
        custom_path = model.get("path")

        tags_str = f" [{', '.join(tags)}]" if tags else ""
        print(f"[{custom_path or model_type}] {name}{tags_str}")

        if dry_run:
            print(f"  [DRY-RUN] Would download from {source}")
            skip_count += 1
            continue

        # Use custom path if provided, otherwise use model type
        if custom_path:
            dest_dir = models_dir / custom_path
        else:
            dest_dir = models_dir / model_type
        handler = handlers.get(source)

        if not handler:
            print(f"  [ERROR] Unknown source: {source}")
            fail_count += 1
            continue

        try:
            # For git source with custom path, clone directly into the path
            if source == "git" and custom_path:
                if handler(model, dest_dir, use_path_directly=True):
                    success_count += 1
                else:
                    fail_count += 1
            elif handler(model, dest_dir):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"  [ERROR] {e}")
            fail_count += 1

    print(f"\n{'='*50}")
    print(f"Sync complete: {success_count} success, {fail_count} failed, {skip_count} skipped")
    return 0 if fail_count == 0 else 1


def add_model(config_path: Path, model_type: str, source: str, **kwargs) -> int:
    """Add a new model to the config file."""
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    if "models" not in config or config["models"] is None:
        config["models"] = []

    model = {"type": model_type, "source": source, **kwargs}
    config["models"].append(model)

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"Added model '{kwargs.get('name', 'unnamed')}' to {config_path}")
    return 0


def list_models(config_path: Path, tag_filter: Optional[str] = None) -> int:
    """List all models in config."""
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return 1

    with open(config_path) as f:
        config = yaml.safe_load(f)

    models = config.get("models", [])
    if not models:
        print("No models defined.")
        return 0

    # Filter by tag if specified
    if tag_filter:
        tag_filter_lower = tag_filter.lower()
        models = [m for m in models if any(tag_filter_lower == t.lower() for t in m.get("tags", []))]

    # Collect all unique tags
    all_tags = set()
    for model in models:
        all_tags.update(model.get("tags", []))

    print(f"{'Name':<25} {'Type/Path':<20} {'Source':<12} {'Tags':<20}")
    print("=" * 77)
    for model in models:
        name = model.get("name", "unnamed")[:24]
        model_type = (model.get("path") or model.get("type", "checkpoints"))[:19]
        source = model.get("source", "url")[:11]
        tags = ", ".join(model.get("tags", []))[:19]
        print(f"{name:<25} {model_type:<20} {source:<12} {tags:<20}")

    if all_tags:
        print(f"\nAvailable tags: {', '.join(sorted(all_tags))}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Declarative model management for ComfyUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  comfy-models-sync                     # Sync all models from models.yaml
  comfy-models-sync --dry-run           # Show what would be downloaded
  comfy-models-sync --filter sdxl       # Only sync models with 'sdxl' in name
  comfy-models-sync --tag video         # Only sync models tagged 'video'
  comfy-models-sync --tag audio         # Only sync models tagged 'audio'
  comfy-models-sync list                # List all configured models
  comfy-models-sync list --tag video    # List models with 'video' tag
  comfy-models-sync add --name "my_model" --type checkpoints --source url --url "https://..."
        """
    )
    
    parser.add_argument("action", nargs="?", default="sync",
                        choices=["sync", "list", "add"],
                        help="Action to perform (default: sync)")
    parser.add_argument("-c", "--config", default="models.yaml",
                        help="Path to models config file (default: models.yaml)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be downloaded without actually downloading")
    parser.add_argument("--filter", dest="model_filter",
                        help="Only sync models matching this name filter")
    parser.add_argument("--tag", "-t", dest="tag_filter",
                        help="Only sync/list models with this tag")
    
    # Add model arguments
    parser.add_argument("--name", help="Model name (for add action)")
    parser.add_argument("--type", dest="model_type", default="checkpoints",
                        help="Model type/destination folder")
    parser.add_argument("--source", default="url",
                        choices=["huggingface", "civitai", "github", "git", "url"],
                        help="Download source")
    parser.add_argument("--url", help="Direct download URL")
    parser.add_argument("--repo", help="Repository (HuggingFace/GitHub)")
    parser.add_argument("--file", help="Specific file to download from repo")
    parser.add_argument("--model-id", type=int, help="CivitAI model ID")
    parser.add_argument("--version-id", type=int, help="CivitAI version ID")

    args = parser.parse_args()
    
    workspace = get_workspace()
    config_path = workspace / args.config

    if args.action == "sync":
        return sync_models(config_path, args.dry_run, args.model_filter, args.tag_filter)
    elif args.action == "list":
        return list_models(config_path, args.tag_filter)
    elif args.action == "add":
        if not args.name:
            print("Error: --name is required for add action")
            return 1
        kwargs = {"name": args.name}
        if args.url:
            kwargs["url"] = args.url
        if args.repo:
            kwargs["repo"] = args.repo
        if args.file:
            kwargs["file"] = args.file
        if args.model_id:
            kwargs["model_id"] = args.model_id
        if args.version_id:
            kwargs["version_id"] = args.version_id
        return add_model(config_path, args.model_type, args.source, **kwargs)

    return 0


if __name__ == "__main__":
    sys.exit(main())
