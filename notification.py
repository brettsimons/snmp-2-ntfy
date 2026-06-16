"""Common notification types for snmp-2-ntfy."""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TrapNotification:
    """Ready-to-send ntfy notification."""
    title: str
    message: str
    priority: str
    tags: list[str] = field(default_factory=list)


class TrapHandler(ABC):
    """Base class for SNMP trap handlers.

    Subclasses define OID mappings and severity logic; the base class
    provides common var-bind parsing and notification assembly.
    """

    enterprise_oid: str          # OID prefix used to match incoming traps
    trap_vars: dict[str, str]    # OID → friendly-name mapping
    priority_map: dict[str, str] # severity name → ntfy priority
    severity_tags: dict[str, str] # severity name → ntfy tag emoji name
    base_tag: str                # default tag included on every notification
    default_label: str           # fallback label if env var is unset
    label_env_var: str           # env var name for the label override

    def __init__(self, priority_override: str = "", extra_tags: list[str] | None = None) -> None:
        self.label = os.getenv(self.label_env_var, self.default_label)
        self.priority_override = priority_override
        self.extra_tags = extra_tags or []

    # -- shared helpers -----------------------------------------------------

    def resolve_var(self, oid: str) -> str:
        """Resolve a trap variable OID to a human-readable field name."""
        return self.trap_vars.get(oid, oid)

    def parse_var_binds(self, var_binds: list) -> dict[str, str]:
        """Extract key-value pairs from SNMP trap variable bindings."""
        return {
            self.resolve_var(oid.prettyPrint()): val.prettyPrint()
            for oid, val in var_binds
        }

    def build_notification(
        self,
        alert_msg: str,
        body_lines: list[str],
        severity_name: str,
        is_resolved: bool = False,
    ) -> TrapNotification:
        """Assemble a TrapNotification from source-agnostic fields."""
        if is_resolved:
            title = f"{self.label}: [Resolved] {alert_msg}"
        else:
            title = f"{self.label}: {alert_msg}"

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        body_lines.append(f"Time: {timestamp}")
        message = "\n".join(body_lines)

        if is_resolved:
            priority = self.priority_override or "low"
        else:
            priority = self.priority_override or self.priority_map.get(severity_name, "default")

        tags = [self.base_tag]
        if is_resolved:
            tags.append("white_check_mark")
        elif severity_name in self.severity_tags:
            tags.append(self.severity_tags[severity_name])
        tags.extend(self.extra_tags)

        return TrapNotification(title=title, message=message, priority=priority, tags=tags)

    # -- abstract interface -------------------------------------------------

    @abstractmethod
    def handle(self, var_binds: list, trap_oid: str, source_addr: str) -> TrapNotification:
        """Parse raw var-binds and return a ready-to-send notification."""
