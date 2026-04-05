'''
Cyber DEM Static Attack Script (Attacker)

Cyber DEM Python

Copyright 2021 Carnegie Mellon University.

NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING INSTITUTE
MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON UNIVERSITY MAKES NO
WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS TO ANY MATTER
INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE OR
MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE MATERIAL.
CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND WITH RESPECT
TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.

Released under a MIT (SEI)-style license, please see license.txt or contact
permission@sei.cmu.edu for full terms.

[DISTRIBUTION STATEMENT A] This material has been approved for public release
and unlimited distribution.  Please see Copyright notice for non-US Government
use and distribution.

DM20-0711
'''


import json
import socket
import time
from cyberdem import base, filesystem

file_system = filesystem.FileSystem('./attacker-sim')
file_system.load_flatfile('./attack_script.json')

# Defending simulation information
HOST = '127.0.0.1'
PORT = 65432

# Pre-scripted attack action order
attack_actions = [
    "86c75da8-8087-4216-9838-c60c36e61ac2",
    "e84ca7b3-e599-4346-9a12-f84dc1d2105f",
    "e86d2d68-0ce7-46b4-b1fa-4baafe286bee"]


def send_attack(action):
    """Send an attack action to the listening defending simulation."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        json_action = json.dumps(action._serialize())
        s.sendall(bytes(json_action, "utf-8"))
        data = json.loads(str(s.recv(1024), "utf-8"))
        time.sleep(2)
        if isinstance(data, dict):
            cdem_obj = base.load_cyberdem_object(data)
            print(f'\nFROM {HOST}: {cdem_obj}')
        else:
            print(f'\nFROM {HOST}: {data}')


if __name__ == "__main__":
    for attack_id in attack_actions:
        attack = file_system.get(attack_id)
        print(
            f'\nACTION: {attack._type} SENT TO {HOST}:{PORT}. TARGETS: '
            f'{attack.targets}')
        send_attack(attack)
        time.sleep(3)
