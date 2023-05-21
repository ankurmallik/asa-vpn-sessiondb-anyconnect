import logging
import time
from netmiko import ConnectHandler
import paramiko
from fetch_creds import get_creds

logging.basicConfig(filename='asa_log.log', level=logging.INFO)

def command_exec(device, max_retries=3):
    net_connect = None
    retries = 0
    while retries < max_retries:
        try:
            net_connect = ConnectHandler(**device)
            logging.info(f"Gathering information from {device['host']}")
            output = net_connect.send_command("show vpn-sessiondb anyconnect", use_textfsm=True, expect_string=r"#", read_timeout=60.0)
            net_connect.disconnect()
            return output
        except (paramiko.ssh_exception.NoValidConnectionsError,
                paramiko.ssh_exception.AuthenticationException) as e:
            logging.error(f"Failed to connect to {device['host']} due to {e}")
            return None
        except paramiko.ssh_exception.SSHException as e:
            if "Error reading SSH protocol banner" in str(e):
                logging.error(f"Failed to connect to {device['host']} due to {e}")
                return None
            else:
                retries += 1
                time.sleep(5)  # wait before trying to reconnect
    logging.error(f"Failed to connect to {device['host']} after {max_retries} retries")
    return None
