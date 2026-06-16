#!/usr/bin/env python3
"""
snmp-2-ntfy — SNMP trap receiver that forwards alerts to ntfy.

Listens for SNMP v1/v2c traps from Dell iDRAC and TrueNAS and posts them
to a configurable ntfy topic using Bearer-token authentication.
"""

import logging
import os
import signal
import sys
import threading

import requests
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv

from idrac_oids import IDRACHandler
from notification import TrapHandler, TrapNotification
from truenas_oids import TrueNASHandler

# ---------------------------------------------------------------------------
# Configuration (all from environment)
# ---------------------------------------------------------------------------
SNMP_LISTEN_ADDRESS = os.getenv("SNMP_LISTEN_ADDRESS", "0.0.0.0")
SNMP_LISTEN_PORT = int(os.getenv("SNMP_LISTEN_PORT", "1162"))
SNMP_COMMUNITIES = [
    community.strip()
    for community in os.getenv("SNMP_COMMUNITIES", "").split(",")
    if community.strip()
]

NTFY_URL = os.getenv("NTFY_URL", "")             # e.g. https://ntfy.example.com
NTFY_TOKEN = os.getenv("NTFY_TOKEN", "")         # Bearer token
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")         # override topic (default: use community)
NTFY_PRIORITY = os.getenv("NTFY_PRIORITY", "")   # optional default priority override
NTFY_TAGS = os.getenv("NTFY_TAGS", "")           # optional extra tags (comma-sep)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("snmp2ntfy")

# ---------------------------------------------------------------------------
# Trap handler dispatch
# ---------------------------------------------------------------------------
_extra_tags = [tag.strip() for tag in NTFY_TAGS.split(",") if tag.strip()] if NTFY_TAGS else []

TRAP_HANDLERS: list[TrapHandler] = [
    IDRACHandler(priority_override=NTFY_PRIORITY, extra_tags=_extra_tags),
    TrueNASHandler(priority_override=NTFY_PRIORITY, extra_tags=_extra_tags),
]


def send_to_ntfy(notification: TrapNotification, topic: str) -> None:
    """Post an alert to the ntfy server."""
    if not NTFY_URL:
        log.error("NTFY_URL is not set — cannot forward alert")
        return

    url = f"{NTFY_URL.rstrip('/')}/{topic}"

    headers = {
        "Title": notification.title,
        "Priority": notification.priority,
        "Tags": ",".join(notification.tags),
        "Authorization": f"Bearer {NTFY_TOKEN}",
    }

    try:
        resp = requests.post(url, data=notification.message.encode("utf-8"), headers=headers, timeout=15)
        resp.raise_for_status()
        log.info("Alert forwarded to ntfy topic '%s' (status %s)", topic, resp.status_code)
    except requests.RequestException as exc:
        log.error("Failed to forward alert to ntfy: %s", exc)


# ---------------------------------------------------------------------------
# SNMP trap callback
# ---------------------------------------------------------------------------
def trap_callback(snmp_engine, state_reference, context_engine_id, context_name,
                  var_binds, cb_ctx):
    """Called by pysnmp whenever a trap/notification is received."""
    transport_domain, transport_address = snmp_engine.msgAndPduDsp.getTransportInfo(state_reference)
    source_addr = f"{transport_address[0]}:{transport_address[1]}" if transport_address else "unknown"

    # Determine ntfy topic from SNMP community (via contextName) or override
    community = context_name.prettyPrint() if context_name else ""
    topic = NTFY_TOPIC or community

    log.info("Trap received from %s (community=%s, topic=%s)", source_addr, community, topic)

    # Identify the trap OID (SNMPv2-MIB::snmpTrapOID.0 = 1.3.6.1.6.3.1.1.4.1.0)
    trap_oid = ""
    for oid, val in var_binds:
        oid_str = oid.prettyPrint()
        if oid_str == "1.3.6.1.6.3.1.1.4.1.0":
            trap_oid = val.prettyPrint()
            break

    log.debug("Trap OID: %s", trap_oid)

    src_addr = transport_address[0] if transport_address else "unknown"

    # Match trap OID to a registered handler
    handler = None
    for candidate in TRAP_HANDLERS:
        if trap_oid.startswith(candidate.enterprise_oid):
            handler = candidate
            break

    if handler is None:
        log.info("Unknown trap source (%s) \u2014 skipping", trap_oid)
        return

    notification = handler.handle(var_binds, trap_oid, src_addr)

    log.info("Forwarding: %s [%s] → topic '%s'", notification.title, notification.priority, topic)

    # Send in a thread to avoid blocking the SNMP engine
    threading.Thread(
        target=send_to_ntfy,
        args=(notification, topic),
        daemon=True,
    ).start()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not NTFY_URL:
        log.error("NTFY_URL environment variable is required")
        sys.exit(1)
    if not SNMP_COMMUNITIES:
        log.error("SNMP_COMMUNITIES environment variable is required")
        sys.exit(1)
    if not NTFY_TOKEN:
        log.warning("NTFY_TOKEN is not set — requests will be unauthenticated")

    log.info("Starting snmp-2-ntfy SNMP trap receiver")
    log.info("  Listen: %s:%s", SNMP_LISTEN_ADDRESS, SNMP_LISTEN_PORT)
    log.info("  Communities: %s", ", ".join(SNMP_COMMUNITIES))
    log.info("  ntfy base URL: %s", NTFY_URL)
    if NTFY_TOPIC:
        log.info("  ntfy topic override: %s", NTFY_TOPIC)
    else:
        log.info("  ntfy topic: mapped from SNMP community")

    # Create SNMP engine
    snmp_engine = engine.SnmpEngine()

    # Transport — listen on UDP
    config.addTransport(
        snmp_engine,
        udp.domainName,
        udp.UdpAsyncioTransport().openServerMode(
            (SNMP_LISTEN_ADDRESS, SNMP_LISTEN_PORT)
        ),
    )

    # SNMPv1/v2c communities — each maps to its own ntfy topic via contextName
    for community in SNMP_COMMUNITIES:
        config.addV1System(
            snmp_engine, f"area-{community}", community, contextName=community
        )

    # Register the callback for incoming notifications
    ntfrcv.NotificationReceiver(snmp_engine, trap_callback)

    log.info("Listening for SNMP traps …")

    # Graceful shutdown
    def shutdown(signum, frame):
        log.info("Shutting down (signal %s) …", signum)
        snmp_engine.transportDispatcher.jobFinished(1)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        snmp_engine.transportDispatcher.jobStarted(1)
        snmp_engine.transportDispatcher.runDispatcher()
    except Exception:
        snmp_engine.transportDispatcher.closeDispatcher()
        raise

    log.info("Stopped.")


if __name__ == "__main__":
    main()
