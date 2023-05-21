# Cisco ASA Data Collection Automation

This Python script automates the process of collecting data from Cisco ASA devices, storing that data in an Excel file, and then sending that data via email.

## Features

- Connects to multiple Cisco ASA devices.
- Collects data using the `show vpn-sessiondb anyconnect` command.
- Stores the data in an Excel file.
- Sends the Excel file via email.
- Encrypts sensitive information such as username and password.
- Uses multithreading to speed up data collection.
- Uses pandas for efficient data manipulation and storage.

## Modules

- `fetch_creds.py`: Handles encryption and decryption of user credentials. The credentials are saved locally to the `ciphertext.bin` file. It's used to secure the user credentials used to connect to the ASA devices.
- `command.py`: Connects to the ASA devices using SSH and executes the `show vpn-sessiondb anyconnect` command to fetch the data. It handles any SSH exceptions and ensures the device connection is closed after fetching the data.
- `data_handler.py`: Uses pandas to handle data processing and stores the fetched data into an Excel file.
- `send_mail.py`: Handles the process of constructing an email, attaching the excel file containing the fetched data, and sending the email to the designated recipients.
- `main.py`: The main script that brings all the above modules together to accomplish the task. It manages the list of devices, triggers the data fetching, storage, and email sending operations.

## Prerequisites

You need to have installed:
- Python 3.7 or later.
- Required libraries: netmiko, paramiko, Cryptodome, pandas. You can install them using the `requirements.txt` file.

## Usage

1. Clone the repository and navigate to the directory.
2. Install the required dependencies: `pip install -r requirements.txt`
3. Run `main.py`: `python3 main.py`

## Disclaimer

The username and password used to connect to the Cisco ASA devices are encrypted and stored in `ciphertext.bin`. Do not delete this file. If running the script for the first time, it will ask for a username and password. Subsequent runs will not require any user input.

The script reads a list of devices (IP addresses or hostnames) from a file called `asa_devices.txt`. Please make sure this file exists in the same directory as `main.py`.

The Excel file and email recipient details are hardcoded into `main.py`. Modify these as needed.

This script is for educational purposes. Always ensure you have permission to access and run commands on any devices before running this script.
