import os
import shutil
import uuid
import yaml
from .utils.network.net_utils import get_network_info
from .utils.core.system_utils import has_hw_virtualization, get_free_loop, generate_password

import ipaddress

config_file_path = ""

def _to_yes_no(val) -> str:
    if isinstance(val, bool):
        return "yes" if val else "no"
    return "yes" if str(val).strip().lower() == "yes" else "no"

def generate_config_file() -> str:

    global config_file_path
    config_file_path = f"/root/openstack-config-{uuid.uuid4().hex}.yaml"
    script_dir = os.path.dirname(os.path.realpath(__file__))
    src_file = os.path.join(script_dir, "templates/conf_template.yaml")
    shutil.copy(src_file, config_file_path)


    return config_file_path


def config_openstack(
    install_horizon: str = "yes",
    install_cinder: str = "yes",
    config_file_path: str = "",
    lvm_image_size_in_gb=None,
    neutron_driver: str = "ovs"   # "ovs" | "ovn"
):
    # Carica template YAML
    try:
        with open(config_file_path, "r") as f:
            config_dict = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config_dict = {}

    # Informazioni di rete
    info = get_network_info()
    iface = info["interface"]
    ip = info["ip"]
    netmask = info["netmask"]
    gateway = info["gateway"]
    ip_cidr = info["network_cidr"]
    network = info["network"]
    last_ip = str(ipaddress.IPv4Address(ipaddress.IPv4Network(ip_cidr, strict=False).broadcast_address - 1))

    if lvm_image_size_in_gb is None:
        lvm_image_size_in_gb = 5

    virt_type = "kvm" if has_hw_virtualization() else "qemu"

    # Password
    config_dict.setdefault("passwords", {})
    for key in ["ADMIN_PASSWORD", "SERVICE_PASSWORD", "RABBITMQ_PASSWORD", "DATABASE_PASSWORD", "DEMO_PASSWORD"]:
        config_dict["passwords"][key] = generate_password()

    # Rete
    config_dict.setdefault("network", {})
    config_dict["network"]["HOST_IP"] = ip
    config_dict["network"]["HOST_IP_NETMASK"] = netmask
    config_dict["network"]["HOST_IP_CIDR"] = ip_cidr

    # Public network
    config_dict.setdefault("public_network", {})
    config_dict["public_network"]["PUBLIC_SUBNET_CIDR"] = network
    config_dict["public_network"]["PUBLIC_SUBNET_RANGE_START"] = ip
    config_dict["public_network"]["PUBLIC_SUBNET_RANGE_END"] = last_ip
    config_dict["public_network"]["PUBLIC_SUBNET_GATEWAY"] = gateway
    config_dict["public_network"]["PUBLIC_SUBNET_DNS_SERVERS"] = "8.8.8.8"

    # Neutron
    config_dict.setdefault("neutron", {})
    config_dict["neutron"]["DRIVER"] = neutron_driver

    # Neutron OVS / OVN
    config_dict["neutron"].setdefault("ovs", {})
    config_dict["neutron"]["ovs"]["CREATE_BRIDGES"] = "yes" if neutron_driver == "ovs" else "no"
    config_dict["neutron"]["ovs"]["PUBLIC_BRIDGE_INTERFACE"] = iface if neutron_driver == "ovs" else ""
    config_dict["neutron"]["ovs"]["PUBLIC_BRIDGE"] = "br-ex" if neutron_driver == "ovs" else ""
    config_dict["neutron"]["ovs"]["INTERNAL_BRIDGE"] = "br-internal" if neutron_driver == "ovs" else ""

    config_dict["neutron"].setdefault("ovn", {})
    if neutron_driver == "ovn":
        config_dict["neutron"]["ovn"].update({
            "CREATE_BRIDGES": "yes",
            "OVN_NB_PORT": 6641,
            "OVN_SB_PORT": 6642,
            "OVN_PUBLIC_BRIDGE_INTERFACE": iface,
            "OVN_PUBLIC_BRIDGE": "br-ex",
            "OVN_ENCAP_TYPE": "geneve",
            "OVN_L3_SCHEDULER": "leastloaded",
            "ENABLE_DISTRIBUTED_FLOATING_IP": False
        })
    else:
        config_dict["neutron"]["ovn"].update({
            "CREATE_BRIDGES": "",
            "OVN_NB_PORT": "",
            "OVN_SB_PORT": "",
            "OVN_PUBLIC_BRIDGE_INTERFACE": "",
            "OVN_PUBLIC_BRIDGE": "",
            "OVN_ENCAP_TYPE": "",
            "OVN_L3_SCHEDULER": "",
            "ENABLE_DISTRIBUTED_FLOATING_IP": False
        })

    # Tenant network
    config_dict["neutron"].setdefault("tenant_network", {})
    config_dict["neutron"]["tenant_network"]["TYPE"] = "geneve" if neutron_driver == "ovn" else "flat"
    config_dict["neutron"]["tenant_network"]["VNI_RANGE"] = "1:65536"

    # Provider networks
    if neutron_driver == "ovs":
        config_dict["neutron"]["provider_networks"] = [
            {"name": "public", "bridge": "br-ex", "type": "flat"},
            {"name": "internal", "bridge": "br-internal", "type": "flat"}
        ]
    else:
        config_dict["neutron"]["provider_networks"] = [
            {"name": "public", "bridge": "br-ex", "type": "flat"}
        ]

    # Cinder
    config_dict.setdefault("cinder", {})
    config_dict.setdefault("optional_services", {})

    config_dict["optional_services"]["INSTALL_CINDER"] = _to_yes_no(install_cinder)
    config_dict["optional_services"]["INSTALL_HORIZON"] = _to_yes_no(install_horizon)

    config_dict["cinder"]["lvm"] = {
        "CINDER_VOLUME_LVM_PHYSICAL_PV_LOOP_NAME": get_free_loop(),
        "CINDER_VOLUME_LVM_IMAGE_FILE_PATH": "/var/lib/cinder/images/cinder-volumes.img",
        "CINDER_VOLUME_LVM_IMAGE_SIZE_IN_GB": lvm_image_size_in_gb
    }

    # Compute
    config_dict.setdefault("compute", {})
    config_dict["compute"]["NOVA_COMPUTE_VIRT_TYPE"] = virt_type
    config_dict["compute"]["CPU_ALLOCATION_RATIO"] = 4.0
    config_dict["compute"]["RAM_ALLOCATION_RATIO"] = 1.5
    config_dict["compute"]["DISK_ALLOCATION_RATIO"] = 1.0

    # OpenStack
    config_dict.setdefault("openstack", {})
    config_dict["openstack"].setdefault("OPENSTACK_RELEASE", "caracal")
    config_dict["openstack"].setdefault("REGION_NAME", "RegionOne")

    # Scrive il file YAML aggiornato
    with open(config_file_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

    