#!/usr/bin/env python3
"""
Smart model downloader for ComfyUI
"""
import os
import sys
import yaml
import requests
from pathlib import Path

def log(message):
    print(f"[ComfyUI] {message}", flush=True)

def download_file(url, filepath, name, min_size=0):
    """Download file with progress bar and validation"""
    if filepath.exists():
        if filepath.stat().st_size >= min_size:
            log(f"{name} already exists, skipping")
            return True
        else:
            log(f"{name} exists but too small, redownloading")
            filepath.unlink()
    
    log(f"Downloading {name}...")
    log(f"URL: {url}")
    log(f"Path: {filepath}")
    
    # Create directory if needed
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Validate file size
        if filepath.stat().st_size >= min_size:
            log(f"{name} downloaded successfully")
            return True
        else:
            log(f"{name} download failed - file too small")
            filepath.unlink()
            return False
            
    except Exception as e:
        log(f"{name} download failed: {e}")
        if filepath.exists():
            filepath.unlink()
        return False

def load_models_config(config_path):
    """Load models configuration from YAML"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        log(f"Failed to load config {config_path}: {e}")
        return None

def download_model_set(models_config, model_set, models_base):
    """Download a specific set of models"""
    if model_set == 'all':
        # Special case: download all model sets except 'all' itself
        log("Downloading ALL model sets...")
        all_success = True
        for key in models_config['models']:
            if key != 'all':  # Skip 'all' to avoid recursion
                log(f"Processing model set: {key}")
                if not download_model_set(models_config, key, models_base):
                    all_success = False
        log(f"All model sets completed: {'SUCCESS' if all_success else 'PARTIAL'}")
        return all_success
    
    if model_set not in models_config['models']:
        log(f"Unknown model set: {model_set}")
        return False
    
    models = models_config['models'][model_set]
    log(f"Downloading {model_set} models ({len(models)} total)...")
    
    success_count = 0
    for model in models:
        filepath = Path(models_base) / model['path']
        min_size = model.get('min_size', 100000000)  # 100MB default
        
        if download_file(model['url'], filepath, model['name'], min_size):
            success_count += 1
    
    log(f"{model_set} downloads completed: {success_count}/{len(models)} successful")
    return success_count == len(models)

def main():
    models_base = "/workspace/ComfyUI/models"
    config_path = "/workspace/models.yaml"
    model_download = os.environ.get('MODEL_DOWNLOAD', 'default')
    
    log(f"Model downloader starting (MODEL_DOWNLOAD={model_download})")
    
    # Create model directories
    for subdir in ['checkpoints', 'vae', 'loras', 'upscale_models', 'controlnet', 'embeddings']:
        Path(models_base, subdir).mkdir(parents=True, exist_ok=True)
    
    if model_download == 'none':
        log("Skipping model downloads (MODEL_DOWNLOAD=none)")
        return True
    
    # Load configuration
    models_config = load_models_config(config_path)
    if not models_config:
        log("Failed to load models configuration, skipping downloads")
        return False
    
    # Download models
    success = download_model_set(models_config, model_download, models_base)
    
    if success:
        log("Model downloader completed successfully")
    else:
        log("Model downloader completed with some failures (continuing anyway)")
    
    # Always return success to avoid restart loops
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
