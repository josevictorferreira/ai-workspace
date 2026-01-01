"""
Flash Attention Shim for Aule Attention

This module creates a fake 'flash_attn' package that wraps Aule Attention,
allowing ComfyUI to use Aule Attention via --use-flash-attention flag.

Usage:
    1. Run this script before starting ComfyUI
    2. Start ComfyUI with: comfy launch -- --use-flash-attention

Or set COMFY_FLASH_ATTN_SHIM=1 environment variable.
"""

import sys
import types
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flash_attn_shim")


def install_shim():
    """Install Aule Attention as flash_attn module."""
    
    # Check if real flash_attn is already installed
    if "flash_attn" in sys.modules:
        logger.warning("flash_attn already loaded, skipping shim installation")
        return False
    
    try:
        from aule import flash_attention
    except ImportError:
        logger.error("Aule Attention not installed. Run: pip install aule-attention")
        return False
    
    # Create fake flash_attn module with proper module attributes
    flash_attn_module = types.ModuleType("flash_attn")
    flash_attn_module.__file__ = __file__
    flash_attn_module.__doc__ = "Aule Attention shim providing flash_attn compatibility"
    flash_attn_module.__package__ = "flash_attn"
    flash_attn_module.__path__ = []
    
    # Create a proper ModuleSpec so packages that check __spec__ don't fail
    from importlib.machinery import ModuleSpec
    flash_attn_module.__spec__ = ModuleSpec(
        name="flash_attn",
        loader=None,
        origin=__file__,
        is_package=True
    )
    
    def flash_attn_func(q, k, v, dropout_p=0.0, causal=False, **kwargs):
        """
        Wrapper around Aule Attention's flash_attention.
        
        Args:
            q: Query tensor [batch, seqlen, heads, head_dim] or [batch, heads, seqlen, head_dim]
            k: Key tensor
            v: Value tensor
            dropout_p: Dropout probability (ignored by Aule)
            causal: Whether to use causal masking
        """
        # Aule Attention expects [batch, heads, seq_len, head_dim]
        # flash_attn uses [batch, seq_len, heads, head_dim]
        # We need to transpose
        
        if len(q.shape) == 4:
            # Check if we need to transpose (ComfyUI sends [batch, seq, heads, dim])
            # Aule expects [batch, heads, seq, dim]
            if q.shape[1] != k.shape[1]:  # heads mismatch, likely need transpose
                q = q.transpose(1, 2)
                k = k.transpose(1, 2)
                v = v.transpose(1, 2)
                output = flash_attention(q, k, v, causal=causal)
                return output.transpose(1, 2)
            else:
                # Try to infer from shape - if dim 1 is likely seq_len (larger)
                # and dim 2 is likely heads (smaller like 8, 12, 16, etc)
                if q.shape[1] > q.shape[2]:  # seq_len > heads
                    q = q.transpose(1, 2)
                    k = k.transpose(1, 2)
                    v = v.transpose(1, 2)
                    output = flash_attention(q, k, v, causal=causal)
                    return output.transpose(1, 2)
        
        return flash_attention(q, k, v, causal=causal)
    
    # Also provide varlen version (stub for compatibility)
    def flash_attn_varlen_func(*args, **kwargs):
        raise NotImplementedError(
            "Variable length attention not supported by Aule Attention shim. "
            "Use regular flash_attn_func instead."
        )
    
    # Attach functions to module
    flash_attn_module.flash_attn_func = flash_attn_func
    flash_attn_module.flash_attn_varlen_func = flash_attn_varlen_func
    
    # Add version info
    flash_attn_module.__version__ = "2.0.0-aule-shim"
    
    # Register main module in sys.modules
    sys.modules["flash_attn"] = flash_attn_module
    
    # Create fake package metadata so importlib.metadata.version() works
    try:
        from importlib.metadata import Distribution, PackageNotFoundError
        import importlib.metadata
        
        class FakeFlashAttnDistribution(Distribution):
            """Fake distribution for flash_attn package metadata."""
            
            @property
            def metadata(self):
                # Return a dict-like object with package metadata
                return {
                    'Name': 'flash-attn',
                    'Version': '2.0.0',
                    'Summary': 'Aule Attention shim providing flash_attn compatibility',
                    'Author': 'Aule Technologies (shim)',
                    'License': 'MIT',
                }
            
            @property
            def name(self):
                return 'flash-attn'
            
            @property
            def version(self):
                return '2.0.0'
            
            def read_text(self, filename):
                if filename == 'METADATA':
                    return "Name: flash-attn\nVersion: 2.0.0\n"
                return None
            
            def locate_file(self, path):
                return __file__
        
        # Monkey-patch importlib.metadata.distribution to return our fake
        _original_distribution = importlib.metadata.distribution
        
        def _patched_distribution(name):
            if name in ('flash_attn', 'flash-attn'):
                return FakeFlashAttnDistribution()
            return _original_distribution(name)
        
        importlib.metadata.distribution = _patched_distribution
        
        # Also patch version() directly for simpler lookups
        _original_version = importlib.metadata.version
        
        def _patched_version(name):
            if name in ('flash_attn', 'flash-attn'):
                return '2.0.0'
            return _original_version(name)
        
        importlib.metadata.version = _patched_version
        
        logger.debug("Patched importlib.metadata for flash_attn")
    except Exception as e:
        logger.warning(f"Could not patch importlib.metadata: {e}")
    
    # Create and register common submodules that packages might import
    # flash_attn.flash_attn_interface
    flash_attn_interface = types.ModuleType("flash_attn.flash_attn_interface")
    flash_attn_interface.__file__ = __file__
    flash_attn_interface.__package__ = "flash_attn"
    flash_attn_interface.__spec__ = ModuleSpec(
        name="flash_attn.flash_attn_interface",
        loader=None,
        origin=__file__,
        is_package=False
    )
    flash_attn_interface.flash_attn_func = flash_attn_func
    flash_attn_interface.flash_attn_varlen_func = flash_attn_varlen_func
    sys.modules["flash_attn.flash_attn_interface"] = flash_attn_interface
    flash_attn_module.flash_attn_interface = flash_attn_interface
    
    # flash_attn.utils
    flash_attn_utils = types.ModuleType("flash_attn.utils")
    flash_attn_utils.__file__ = __file__
    flash_attn_utils.__package__ = "flash_attn"
    flash_attn_utils.__spec__ = ModuleSpec(
        name="flash_attn.utils",
        loader=None,
        origin=__file__,
        is_package=False
    )
    sys.modules["flash_attn.utils"] = flash_attn_utils
    flash_attn_module.utils = flash_attn_utils
    
    logger.info("Flash Attention shim installed (using Aule Attention backend)")
    
    # Show available backends
    try:
        from aule import get_available_backends
        backends = get_available_backends()
        logger.info(f"Available Aule backends: {backends}")
    except:
        pass
    
    return True


def uninstall_shim():
    """Remove the flash_attn shim."""
    if "flash_attn" in sys.modules:
        del sys.modules["flash_attn"]
        logger.info("Flash Attention shim removed")


# Auto-install if run directly or if env var is set
if __name__ == "__main__":
    if install_shim():
        print("Shim installed successfully!")
        print("Now run ComfyUI with: comfy launch -- --use-flash-attention")
else:
    import os
    if os.environ.get("COMFY_FLASH_ATTN_SHIM", "0") == "1":
        install_shim()
