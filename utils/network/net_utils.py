import psutil
import socket
import ipaddress
import subprocess

import os

def is_wifi_interface(iface: str) -> bool:
    try:

        type_path = f"/sys/class/net/{iface}/type"
        if os.path.exists(type_path):
            with open(type_path) as f:
                if f.read().strip() == "801":
                    return True

        if os.path.exists(f"/sys/class/net/{iface}/wireless"):
            return True

        with open("/proc/net/wireless") as f:
            wireless_interfaces = [line.split()[0].strip(":") for line in f.readlines()[2:]]
            if iface in wireless_interfaces:
                return True
    except Exception:
        pass
    return False

def get_default_interface_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

def get_active_interface() -> tuple[str, str]:

    ip = get_default_interface_ip()
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address == ip:
                return iface, ip
    return None, None

def get_network_info():
    iface, ip = get_active_interface()
    if not iface:
        return None

    netmask, broadcast = None, None
    for addr in psutil.net_if_addrs()[iface]:
        if addr.family == socket.AF_INET:
            netmask = addr.netmask
            broadcast = addr.broadcast
            break

    cidr = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False).prefixlen if netmask else None
    network_cidr = f"{ip}/{cidr}" if cidr else None
    network = str(ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)) if netmask else None

    # Trova gateway
    gateway = None
    try:
        route = subprocess.run("ip route", shell=True, capture_output=True, text=True)
        for line in route.stdout.splitlines():
            if line.startswith("default"):
                gateway = line.split()[2]
                break
    except Exception:
        pass

    return {
        "interface": iface,
        "ip": ip,
        "netmask": netmask,
        "cidr": cidr,
        "broadcast": broadcast,
        "gateway": gateway,
        "network_cidr": network_cidr,
        "network": network,
        "is_wifi": is_wifi_interface(iface)
    }
