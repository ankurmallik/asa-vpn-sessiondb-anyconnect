#!/usr/bin/env python3

"""
Python script to collect the output of the SHOW VPN-SESSIONDB ANYCONNECT command from a
set of Cisco ASA firewalls. The output is then saved to a Microsoft Excel file.
"""
import os
from datetime import datetime
from fetch_creds import get_creds
from command import command_exec
from data_handler import collect_in_excel
from concurrent.futures import ThreadPoolExecutor, as_completed
from send_mail import send_email


def main():
    """
    The main() function has the following duties:
     - Reads the devices from asa_devices.txt file
     - Obtains the current date and time.
     - Calls a function to retrieve credentials for the firewalls.
     - Iterates through the devices, calling a function to retieve the desired
       information.
     - Calls a function to save the information to a Microsoft Excel file.
    """
    # fetch username and password
    username, password = get_creds()

    # read the device list
    try:
        with open("asa_devices.txt", "r") as f:
            devices = f.readlines()
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        return

    devices = [x.strip() for x in devices]
    now = datetime.now()
    tab_name = now.strftime("%Y_%m_%d_%H_%M_%S")

    results = []
    with ThreadPoolExecutor() as executor:
        for device in devices:
            device_info = {
                "device_type": "cisco_asa",
                "host": device,
                "username": username,
                "password": password,
            }
            future = executor.submit(command_exec, device_info)
            results.append(future)

        output = []
        for f in as_completed(results):
            vpn_sessiondb = f.result()
            if vpn_sessiondb is not None:
                output.append(vpn_sessiondb)

    # Saving data in excel
    collect_in_excel(tab_name, output)

    # Send the excel file as an email
    from_email = "example@example.com"
    to_list = ["abc@abc.com", "def@def.com"]
    smtp_server = "smtpgw.example.com"
    file_path = r"AnyConnect-Sessions-RAW-Data.xlsx"
    send_email(to_list, file_path, from_email, smtp_server)


if __name__ == "__main__":
    main()
