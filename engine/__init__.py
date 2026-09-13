"""Autonomous browser execution and evidence evaluation."""
import tomllib
from pathlib import Path

VERSION=tomllib.loads((Path(__file__).parent.parent/'pyproject.toml').read_text())['project']['version']
