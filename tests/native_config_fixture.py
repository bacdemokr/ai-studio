"""Model the Gateway config boundary in offline registration/configuration tests."""
import json
from unittest.mock import patch


def apply_config(update, replace_paths):
    import agent_runtime as runtime
    config = json.loads(runtime.config_path().read_text())

    def merge(target, source, prefix=''):
        for key, value in source.items():
            path = prefix + key
            if isinstance(value, dict) and path not in replace_paths:
                merge(target.setdefault(key, {}), value, path + '.')
            else:
                target[key] = value

    merge(config, update)
    runtime.save_config(config)


offline_config = patch('agent_runtime.gateway_config_patch', new=apply_config)
