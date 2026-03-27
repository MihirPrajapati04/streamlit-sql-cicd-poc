"""Expand ${ENV_VAR} placeholders in config strings using the process environment."""

import os
import re

_TEMPLATE = re.compile(r"\$\{([^}]+)\}")


def expand_env_templates(value: str) -> str:
    if not isinstance(value, str):
        return value

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in os.environ or os.environ[name] == "":
            raise KeyError(
                f"Environment variable '{name}' must be set (non-empty) to resolve config templates"
            )
        return os.environ[name]

    return _TEMPLATE.sub(replace, value)
