"""Manage remote machine configurations stored in ~/.flexflow/remotes.json"""

import json
import os
from pathlib import Path


class RemoteConfig:
    """Handle reading and writing remote machine configurations."""

    def __init__(self):
        """Initialize remote config manager."""
        self.config_dir = Path.home() / '.flexflow'
        self.config_file = self.config_dir / 'remotes.json'
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Ensure config directory exists."""
        self.config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _ensure_config_file(self):
        """Ensure config file exists with default structure."""
        if not self.config_file.exists():
            self._write_config({'remotes': []})
        # Set permissions to 600 (owner read/write only)
        os.chmod(self.config_file, 0o600)

    def _read_config(self) -> dict:
        """Read config file. Returns dict with 'remotes' key."""
        self._ensure_config_file()
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            return config
        except (json.JSONDecodeError, IOError) as e:
            raise RuntimeError(f"Error reading remote config: {e}")

    def _write_config(self, config: dict):
        """Write config file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            os.chmod(self.config_file, 0o600)
        except IOError as e:
            raise RuntimeError(f"Error writing remote config: {e}")

    def add_remote(self, name: str, user: str, ip: str, password: str,
                   port: int = 22, path: str = None) -> bool:
        """Add a new remote machine. Returns True if added, False if exists."""
        config = self._read_config()
        
        # Check if remote already exists
        for remote in config['remotes']:
            if remote['name'] == name:
                return False
        
        # Add new remote
        config['remotes'].append({
            'name': name,
            'user': user,
            'ip': ip,
            'port': port,
            'password': password,
            'path': path or ''
        })
        self._write_config(config)
        return True

    def get_remote(self, name: str) -> dict:
        """Get remote by name. Returns dict or None."""
        config = self._read_config()
        for remote in config['remotes']:
            if remote['name'] == name:
                return remote.copy()
        return None

    def get_all_remotes(self) -> list:
        """Get all remotes. Returns list of dicts."""
        config = self._read_config()
        return [r.copy() for r in config['remotes']]

    def update_remote(self, name: str, **kwargs) -> bool:
        """Update remote fields. Returns True if updated, False if not found."""
        config = self._read_config()
        
        for remote in config['remotes']:
            if remote['name'] == name:
                # Update allowed fields only
                allowed_fields = {'user', 'ip', 'port', 'password', 'path'}
                for key, value in kwargs.items():
                    if key in allowed_fields and value is not None:
                        remote[key] = value
                self._write_config(config)
                return True
        return False

    def delete_remote(self, name: str) -> bool:
        """Delete remote. Returns True if deleted, False if not found."""
        config = self._read_config()
        
        original_len = len(config['remotes'])
        config['remotes'] = [r for r in config['remotes'] if r['name'] != name]
        
        if len(config['remotes']) < original_len:
            self._write_config(config)
            return True
        return False

    def remote_exists(self, name: str) -> bool:
        """Check if remote exists."""
        return self.get_remote(name) is not None


# Global instance
_config = None


def get_remote_config() -> RemoteConfig:
    """Get global remote config instance."""
    global _config
    if _config is None:
        _config = RemoteConfig()
    return _config
