import os
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from Cryptodome.Protocol.KDF import PBKDF2
from getpass import getpass

SALT = b'some_random_bytes'

def encrypt(username, password, password_based_key):
    cipher = AES.new(password_based_key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(bytes(username + ':' + password, 'utf-8'))

    with open("ciphertext.bin", "wb") as f:
        [f.write(x) for x in (cipher.nonce, tag, ciphertext)]
    print("The encrypted data is stored in ciphertext.bin")

def decrypt(password_based_key):
    with open("ciphertext.bin", "rb") as f:
        nonce, tag, ciphertext = [f.read(x) for x in (16, 16, -1)]

    cipher = AES.new(password_based_key, AES.MODE_EAX, nonce=nonce)
    data = cipher.decrypt_and_verify(ciphertext, tag)
    username, password = data.decode("utf-8").split(":")
    return username, password

def get_creds():
    username = input("Enter username: ")
    password = getpass("Enter password: ")  # More secure than input()
    password_based_key = PBKDF2(password, SALT, 16)  # Derive key

    if os.path.isfile('ciphertext.bin'):
        username, password = decrypt(password_based_key)
    else:
        encrypt(username, password, password_based_key)
        username, password = decrypt(password_based_key)

    return username, password
