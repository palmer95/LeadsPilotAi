# config_utils.py
import os, requests, logging
from typing import Dict

CONFIG_BASE_URL = os.getenv("CONFIG_BASE_URL", "https://www.leadspilotai.com")
_config_cache: Dict[str, dict] = {}
logger = logging.getLogger(__name__)

def get_config(company: str) -> dict:
    if company not in _config_cache:
        url = f"{CONFIG_BASE_URL}/client-configs/{company}.json"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            config = resp.json()
            required_fields = ["business_name", "packages", "qualifying_questions"]
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required config field: {field}")
            for pkg in config.get("packages", []):
                pkg_name = pkg.get("name", "")
                if not pkg_name or not all(c.isalnum() or c in " -_" for c in pkg_name):
                    raise ValueError(f"Invalid package name: {pkg_name}")
            _config_cache[company] = config
        except requests.RequestException as e:
            logger.error(f"Failed to fetch config for {company}: {e}")
            raise FileNotFoundError(f"Could not fetch config: {url} → {e}")
        except ValueError as e:
            logger.error(f"Invalid config for {company}: {e}")
            raise
    return _config_cache[company]
