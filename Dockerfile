FROM python:3.12-slim

LABEL maintainer="snmp-2-ntfy"
LABEL description="SNMP trap receiver that forwards iDRAC and TrueNAS alerts to ntfy"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY idrac_oids.py truenas_oids.py notification.py trap_receiver.py ./

# SNMP trap port
EXPOSE 162/udp

RUN useradd --system --no-create-home trapuser
USER trapuser

ENTRYPOINT ["python", "-u", "trap_receiver.py"]
