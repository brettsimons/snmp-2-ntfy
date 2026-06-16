"""
TrueNAS SNMP OID mappings for human-readable alert messages.

Reference: TRUENAS-MIB (enterprises.50536)
Enterprise OID: 1.3.6.1.4.1.50536
"""

from notification import TrapHandler, TrapNotification

# iXsystems / TrueNAS enterprise OID prefix
TRUENAS_ENTERPRISE_OID = "1.3.6.1.4.1.50536"

# Notification trap OIDs
_ALERT_CANCELLATION_OID = "1.3.6.1.4.1.50536.2.1.2"

# AlertLevelType from TRUENAS-MIB
_ALERT_LEVEL_MAP = {
    1: ("info", "ℹ️"),
    2: ("notice", "📝"),
    3: ("warning", "⚠️"),
    4: ("error", "🔴"),
    5: ("critical", "🔴"),
    6: ("alert", "🚨"),
    7: ("emergency", "🚨"),
}


class TrueNASHandler(TrapHandler):
    """SNMP trap handler for TrueNAS alerts."""

    enterprise_oid = TRUENAS_ENTERPRISE_OID
    base_tag = "floppy_disk"
    default_label = "TrueNAS"
    label_env_var = "TRUENAS_LABEL"

    trap_vars = {
        "1.3.6.1.4.1.50536.2.2.1": "alertId",
        "1.3.6.1.4.1.50536.2.2.2": "alertLevel",
        "1.3.6.1.4.1.50536.2.2.3": "alertMessage",
    }

    priority_map = {
        "info": "low",
        "notice": "default",
        "warning": "high",
        "error": "high",
        "critical": "urgent",
        "alert": "urgent",
        "emergency": "urgent",
    }

    severity_tags = {
        "critical": "rotating_light",
        "alert": "rotating_light",
        "emergency": "rotating_light",
        "warning": "warning",
        "error": "warning",
        "info": "information_source",
    }

    def handle(self, var_binds: list, trap_oid: str, source_addr: str) -> TrapNotification:
        parsed = self.parse_var_binds(var_binds)
        is_cancellation = trap_oid == _ALERT_CANCELLATION_OID

        level_str = parsed.get("alertLevel", "")
        try:
            level_code = int(level_str)
        except (ValueError, TypeError):
            level_code = 0
        level_name, _ = _ALERT_LEVEL_MAP.get(level_code, ("unknown", "❓"))

        alert_msg = parsed.get("alertMessage", "No message provided")
        alert_id = parsed.get("alertId", "N/A")

        return self.build_notification(
            alert_msg,
            [f"Host: {source_addr}", f"Alert ID: {alert_id}", f"Level: {level_name}"],
            level_name,
            is_resolved=is_cancellation,
        )
