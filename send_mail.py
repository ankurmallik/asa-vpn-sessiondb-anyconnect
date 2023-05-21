import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

def send_email(to_list, file_path, from_email, smtp_server, port=25):
    """
    Sends an email with an attachment to a list of recipients using SMTP on TCP port 25 with no TLS
    Args:
        to_list (list): list of recipients
        file_path (str): path to the excel file
        from_email (str): sender's email address
        smtp_server (str): SMTP server address
        port (int): port number, default is 25
    """
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = ", ".join(to_list)
    msg['Subject'] = "AnyConnect VPN Sessions Data"

    # Open the excel file as a binary file
    with open(file_path, 'rb') as f:
        payload = MIMEBase("application", "octet-stream", Name=file_path)
        payload.set_payload((f).read())

    # Encode the binary into base64
    encoders.encode_base64(payload)

    # Add header with pdf name
    payload.add_header("Content-Disposition", "attachment", filename=file_path)
    msg.attach(payload)

    # Connect to the server and send the email
    try:
        server = smtplib.SMTP(smtp_server, port)
        server.sendmail(from_email, to_list, msg.as_string())
        server.quit()
    except smtplib.SMTPException as e:
        print(f"Error occurred while sending email: {e}")
