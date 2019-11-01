# Author: Rodrigo Graca

import Constants
from Constants import DisplayCommands, SocketCommands

import json
import socket
import struct
import time
import threading
import select

from requests import get
from base64 import b64encode, b64decode
from Crypto.Cipher import AES
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

# server_addr = (internal_IP, 65532)


class CryptoError(Exception):
    pass


class Client(threading.Thread):

    def __init__(self, server_addr=('localhost', 65532), serverTimeout=1, recvTimeout=1, daemon=True):

        # Getting the local address of the computer in the network
        super(Client, self).__init__(daemon=daemon)
        self.local_hostname = socket.gethostname()
        self.internal_IP = socket.gethostbyname(self.local_hostname)

        # Getting the external address of the network (Site may not always work)
        self.external_IP = get('https://api.ipify.org', timeout=10).text

        # Controls if the thread is functioning
        self.running = True

        # Flag to transmit
        self.readyToTransmit = False

        # Program commands to run
        self.commands = {SocketCommands.DISPLAY: self.displayText}

        # What should be displayed as the server's name in 'output'
        self.identifier = "Server: "

        # In Bytes
        self.RSA_KEY_LENGTH = Constants.RSA_KEY_LENGTH
        self.AES_KEY_LENGTH = Constants.AES_KEY_LENGTH

        # Server address to connect to
        self.server_addr = server_addr

        # Server Conn
        self.SERVER_CONN_TIMEOUT = serverTimeout  # How long to wait in between server pings
        self.SERVER_MAX_ATTEMPTS = 10

        # How long to wait for a response from the server before preforming other tasks
        self.RECV_TIMEOUT = recvTimeout

        # Write and read lists to allow easier threading
        self.received = []  # Read
        self.send = []  # Write

        # Lock to prevent corruption of the above list
        self.recvLock = threading.Lock()
        self.sendLock = threading.Lock()

    def run(self):

        self.addToDisplay(">>>RSA KEY LENGTH -> " + str(self.RSA_KEY_LENGTH) + " bytes<<<")
        self.addToDisplay(">>>AES KEY LENGTH (EAX MODE) -> " + str(self.AES_KEY_LENGTH) + " bytes<<<")

        self.addToDisplay("Searching for a connection...")

        # Setup socket for usage
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.addToDisplay("Client on %s at Internal IP of: %s and External IP of: %s" % (
            self.local_hostname, self.internal_IP, self.external_IP
        ))

        # Limit the amount of times we spam a particular IP and how often
        tries = 0
        while True:
            if tries >= self.SERVER_MAX_ATTEMPTS:
                self.addToDisplay("Server could not be reached. Make sure of your connection?")
                self.addToDisplay("Exiting...")
                self.exit()
                break
            try:
                client.connect(self.server_addr)
                break
            except Exception:
                pass
            tries += 1
            time.sleep(self.SERVER_CONN_TIMEOUT)

        if self.running:
            self.addToDisplay('----------------------------------')
            self.addToDisplay("Connection found!\n")
            self.addToDisplay("Server at IP address of %s" % self.server_addr[0])

            # TODO Method to confirm server identity, otherwise use pre-shared keys

            # Generate all the keys and RSA cipher needed to start communications
            self.addToDisplay('Creating RSA keys for connection')
            private_key = RSA.generate(self.RSA_KEY_LENGTH)
            rsa_cipher = PKCS1_OAEP.new(private_key)
            self.addToDisplay('Keys and cipher created')

            self.addToDisplay('Creating AES key for connection')
            client_aes_key = get_random_bytes(self.AES_KEY_LENGTH)
            self.addToDisplay('AES key created')

            try:
                self.addToDisplay("Trading keys...")
                server_rsa_cipher, server_aes_key = self.setup_AES(client, private_key, rsa_cipher, client_aes_key)
                self.addToDisplay("Keys traded!")

                self.addToDisplay(DisplayCommands.clearOutput)

                # Start the send/recv loop
                self.beginCommunication(client, server_aes_key, client_aes_key)

            except socket.error as e:
                print('>>>Connection Error<<<')
                print(e)
                self.exit()
        client.close()

    def beginCommunication(self, client, server_aes_key, client_aes_key):

        self.readyToTransmit = True

        # Wait however long the timeout is for a response in buffer
        # Then continue executing code if none is found
        while self.running:
            ready = select.select([client], [], [], self.RECV_TIMEOUT)
            if ready[0]:
                data = self.recv_encrypted(client, server_aes_key)
                print(data)
                command = data['command']

                # TODO Add change username command
                # If the data refers to a command like 'change username' then execute that and don't display
                if command in self.commands:
                    self.commands[command](client, client_aes_key, data)
                else:

                    if data == b'':
                        self.exit()
                        break

            else:
                # print("No data")
                pass

            while self.getSendTotal() > 0:
                msg = self.nextToSend()
                self.send_encrypted(client, client_aes_key, msg, SocketCommands.DISPLAY)

    def addToDisplay(self, msg):
        self.recvLock.acquire()

        self.received.append(msg)

        self.recvLock.release()

    def nextToDisplay(self):
        self.recvLock.acquire()

        if len(self.received) > 0:

            toDisplay = self.received.pop(0)
            self.recvLock.release()
            return toDisplay
        else:
            self.recvLock.release()
            return None

    def getRecvTotal(self):
        self.recvLock.acquire()

        total = len(self.received)

        self.recvLock.release()

        return total

    def addToSend(self, msg):
        self.sendLock.acquire()

        self.send.append(msg)

        self.sendLock.release()

    def nextToSend(self):
        self.sendLock.acquire()

        if len(self.send) > 0:

            toSend = self.send.pop(0)
            self.sendLock.release()
            return toSend
        else:
            self.sendLock.release()
            return None

    def getSendTotal(self):
        self.sendLock.acquire()

        total = len(self.send)

        self.sendLock.release()

        return total

    def displayText(self, client, client_aes_key, data):
        # TODO Define different decoding like UTF-32

        text = data['data']
        self.addToDisplay(self.identifier + text)

    def sendFile(self, filePath):
        self.addToDisplay(SocketCommands.FILE_SEND)

    def send_to(self, client, data):
        # Get length of data and append so we can receive all data
        length = struct.pack('>I', len(data))
        formatted_data = length + data

        try:
            # Send data to server, str encoded as bytes
            client.send(formatted_data)
            return True
        except Exception as e:
            print(e)
            return False

    def recv_all(self, client, len_bytes):
        # Helper function to receive number bytes or return None if EOF is hit
        data = b''
        while len(data) < len_bytes:
            packet = client.recv(len_bytes - len(data))
            if not packet:
                return None
            data += packet
        return data

    def recv_from(self, client):
        # Read message length and unpack it into an integer
        raw_data_len = self.recv_all(client, 4)
        if not raw_data_len:
            return None
        data_len = struct.unpack('>I', raw_data_len)[0]
        # Read the message data
        return self.recv_all(client, data_len)

    def recv_encrypted(self, client, client_aes_key):

        formatted_data = self.recv_from(client)

        if formatted_data is None:
            return b''

        datab64 = json.loads(formatted_data)

        client_aes_cipher = AES.new(
            client_aes_key,
            AES.MODE_EAX,
            nonce=b64decode(
                datab64['nonce']
            ))
        client_aes_cipher.update(
            b64decode(
                datab64['header']
            ))

        cipher_text = b64decode(datab64['cipher_text'])
        MAC = b64decode(datab64['MAC'])

        data = json.loads(client_aes_cipher.decrypt_and_verify(cipher_text, MAC))

        result = {'command': data['com'], 'data': data['data']}

        return result

    def send_encrypted(self, client, server_aes_key, data, command: SocketCommands):

        # Return random bytes for header and set up EAX mode with random 256 bit IV, MAC length 128 bits
        header = get_random_bytes(16)
        client_aes_cipher = AES.new(server_aes_key, AES.MODE_EAX, nonce=get_random_bytes(32), mac_len=16)

        # Update EAX mode AES header
        client_aes_cipher.update(header)

        data = json.dumps({
            'com': command,
            'data': data
        }).encode()

        # Encrypt the message. Returns the encrypted message with MAC tag to verify
        cipher_text, tag = client_aes_cipher.encrypt_and_digest(data)

        # json.dumps() returns dictionary as string and .encode() translates str to bytes
        cipher_json = json.dumps({
            'nonce': b64encode(client_aes_cipher.nonce).decode('utf-8'),
            'cipher_text': b64encode(cipher_text).decode('utf-8'),
            'header': b64encode(header).decode('utf-8'),
            'MAC': b64encode(tag).decode('utf-8')
        }).encode()

        # Send to the server and return success
        return self.send_to(client, cipher_json)

    def setup_AES(self, server, client_key, client_cipher, client_aes_key):

        global AES_READY
        # Receive the server's public key
        server_public = self.recv_from(server)

        # Setup RSA cipher to encrypt AES keys using server public key
        server_key = RSA.import_key(server_public)
        server_rsa_cipher = PKCS1_OAEP.new(server_key)

        # Send server our public key so can encrypt and AES keys won't be leaked
        self.send_to(server, client_key.publickey().export_key())

        # Send server AES key
        self.send_to(server, server_rsa_cipher.encrypt(client_aes_key))

        # Receive and decrypt the server's AES key
        server_aes_key = client_cipher.decrypt(self.recv_from(server))

        AES_READY = True

        return server_rsa_cipher, server_aes_key

    def exit(self):
        self.running = False

    def isRunning(self):
        return self.running
