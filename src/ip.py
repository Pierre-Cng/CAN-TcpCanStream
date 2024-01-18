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
