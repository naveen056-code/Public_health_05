"""Top-level ADK entrypoint re-exporting the authoritative clinic_broker multi-agent pipeline."""

from .clinic_broker.agent import root_agent

__all__ = ["root_agent"]
