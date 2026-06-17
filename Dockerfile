FROM python:3.12-slim

LABEL maintainer="snmp-2-ntfy"
LABEL description="SNMP trap receiver that forwards iDRAC and TrueNAS alerts to ntfy"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY idrac_oids.py truenas_oids.py notification.py trap_receiver.py ./

# SNMP trap port
EXPOSE 162/udp

RUN apt-get update && apt-get install -y --no-install-recommends libcap2-bin \
    && setcap 'cap_net_bind_service=+ep' $(readlink -f /usr/local/bin/python3) \
    && apt-get purge -y libcap2-bin && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

RUN useradd --system --no-create-home trapuser
USER trapuser

ENTRYPOINT ["python", "-u", "trap_receiver.py"]
