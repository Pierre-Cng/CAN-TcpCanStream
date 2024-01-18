'''
import netifaces

def get_gateway_ip():
    try:
        # Get a list of network interfaces
        interfaces = netifaces.interfaces()

        # Find the default gateway IP address
        for interface in interfaces:
            addrs = netifaces.ifaddresses(interface)
            gateway_info = addrs.get(netifaces.AF_INET, [])
            for info in gateway_info:
                if 'peer' in info:
                    return info['peer']

    except Exception as e:
        return str(e)

# Get and print the gateway IP address
gateway_ip = get_gateway_ip()
print("Gateway IP Address:", gateway_ip)
'''
import socket, struct

def get_default_gateway_linux():
    """Read the default gateway directly from /proc."""
    with open("/proc/net/route") as fh:
        for line in fh:
            fields = line.strip().split()
            if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                # If not default route or not RTF_GATEWAY, skip it
                continue

            return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))