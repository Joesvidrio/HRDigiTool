"""
Utility functions for file path management and resource loading.

This module provides helpers to resolve absolute paths for resources, 
ensuring compatibility between standard local development environments 
and packaged executables (e.g., PyInstaller).
"""

import os
import sys


def get_resource_path(relative_path: str) -> str:
    """
    Gets the absolute path to a resource.
    
    This function intelligently resolves file paths depending on whether the 
    application is running directly from the source code or as a frozen 
    executable bundled by PyInstaller.
    
    Args:
        relative_path (str): The relative path to the requested resource.
        
    Returns:
        str: The absolute path to the resource.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller extracts resources to sys._MEIPASS
        base_path = sys._MEIPASS
    else:
        # In local development
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, relative_path)