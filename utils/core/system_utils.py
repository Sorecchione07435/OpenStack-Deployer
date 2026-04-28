
import random
import string
import socket
from time import sleep, time

from . import colors

import subprocess

def nc_wait(addr: str, port: int, timeout: int = 30) -> bool:

    start_time = time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    while True:
        if sock.connect_ex((addr, port)) == 0:
            sock.close()
            return True
        elif time() - start_time > timeout:
            print(f"{colors.RED}ERROR:{colors.RESET} Service at {addr}:{port} did not respond within {timeout} seconds.")
            sock.close()
            return False
        sleep(1)

def has_hw_virtualization():
    try:
        with open("/proc/cpuinfo") as f:
            cpuinfo = f.read()

        cpu_support = ("vmx" in cpuinfo) or ("svm" in cpuinfo)

        kvm_available = False
        try:
            open("/dev/kvm").close()
            kvm_available = True
        except:
            pass

        return cpu_support and kvm_available

    except:
        return False

def get_free_loop():
    loop = subprocess.check_output(["losetup", "-f"]).decode().strip()
    return loop

def generate_password(length=12):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))
