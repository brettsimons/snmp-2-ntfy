"""
Dell iDRAC SNMP OID mappings for human-readable alert messages.

Reference: Dell iDRAC MIB (IDRAC-MIB-SMIv2)
Enterprise OID: 1.3.6.1.4.1.674.10892.5
MIB browser: https://mibs.observium.org/mib/IDRAC-MIB-SMIv2/
"""

from notification import TrapHandler, TrapNotification

# Dell enterprise OID prefix
DELL_ENTERPRISE_OID = "1.3.6.1.4.1.674"

# ObjectStatusEnum from IDRAC-MIB-SMIv2
_SEVERITY_MAP = {
    1: ("other", "ℹ️"),
    2: ("unknown", "❓"),
    3: ("ok", "✅"),
    4: ("nonCritical", "⚠️"),
    5: ("critical", "🔴"),
    6: ("nonRecoverable", "🚨"),
}


class IDRACHandler(TrapHandler):
    """SNMP trap handler for Dell iDRAC alerts."""

    enterprise_oid = DELL_ENTERPRISE_OID
    base_tag = "server"
    default_label = "iDRAC"
    label_env_var = "IDRAC_LABEL"

    # Alert variable OIDs from alertVariablesGroup (.1.3.6.1.4.1.674.10892.5.3.1)
    # Trap varbinds arrive with a .0 scalar instance suffix.
    trap_vars = {
        "1.3.6.1.4.1.674.10892.5.3.1.1.0": "alertMessageID",
        "1.3.6.1.4.1.674.10892.5.3.1.2.0": "alertMessage",
        "1.3.6.1.4.1.674.10892.5.3.1.3.0": "alertCurrentStatus",
        "1.3.6.1.4.1.674.10892.5.3.1.4.0": "alertSystemServiceTag",
        "1.3.6.1.4.1.674.10892.5.3.1.5.0": "alertSystemFQDN",
        "1.3.6.1.4.1.674.10892.5.3.1.6.0": "alertFQDD",
        "1.3.6.1.4.1.674.10892.5.3.1.7.0": "alertDeviceDisplayName",
        "1.3.6.1.4.1.674.10892.5.3.1.8.0": "alertMessageArguments",
        "1.3.6.1.4.1.674.10892.5.3.1.9.0": "alertChassisServiceTag",
        "1.3.6.1.4.1.674.10892.5.3.1.10.0": "alertChassisName",
        "1.3.6.1.4.1.674.10892.5.3.1.11.0": "alertRacFQDN",
    }

    priority_map = {
        "ok": "low",
        "other": "default",
        "unknown": "default",
        "nonCritical": "high",
        "critical": "urgent",
        "nonRecoverable": "urgent",
    }

    severity_tags = {
        "critical": "rotating_light",
        "nonRecoverable": "rotating_light",
        "nonCritical": "warning",
        "ok": "white_check_mark",
    }

    def handle(self, var_binds: list, trap_oid: str, source_addr: str) -> TrapNotification:
        parsed = self.parse_var_binds(var_binds)

        status_str = parsed.get("alertCurrentStatus", "")
        try:
            status_code = int(status_str)
        except (ValueError, TypeError):
            status_code = 0
        severity_name, _ = _SEVERITY_MAP.get(status_code, ("unknown", "❓"))

        msg_id = parsed.get("alertMessageID") or "N/A"
        alert_msg = parsed.get("alertMessage") or "No message provided"
        fqdn = parsed.get("alertSystemFQDN") or parsed.get("alertRacFQDN") or source_addr
        svc_tag = parsed.get("alertSystemServiceTag") or parsed.get("alertChassisServiceTag") or "N/A"

        return self.build_notification(
            alert_msg,
            [f"Message ID: {msg_id}", f"Host: {fqdn}", f"Service Tag: {svc_tag}", f"Severity: {severity_name}"],
            severity_name,
        )
