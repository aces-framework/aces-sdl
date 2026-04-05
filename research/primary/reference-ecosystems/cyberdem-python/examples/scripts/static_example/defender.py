'''
Cyber DEM Static Attack Script (Defender)

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

file_system = filesystem.FileSystem('./defender-sim')
file_system.load_flatfile('../../test_files/sample_net_1.json')


def respond(event):
    if event._type == "PhishingAttack":
        # Install malware (HMI "update")
        cdem_obj = base.Data(
            data_type='Code', name='HMI Update',
            description='HMI vendor update')
        # Get HMI
        net_obj = file_system.get("b0ee2f75-0b7e-44f6-a27d-2374700989e6")
        rel = base.Relationship(cdem_obj.id, net_obj.id, 'ResidesOn')
        file_system.save(cdem_obj)
        file_system.save(rel)
        print(
            f'LOG: New Object ({cdem_obj._type}) {cdem_obj.name}')
        # Malware C2 back to the attacker
        cdem_obj = base.Data(
            name="Reverse channel",
            description="Representing data packets beaconing from malware")
        rel = base.Relationship(cdem_obj.id, net_obj.id, 'ResidesOn')
        file_system.save(cdem_obj)
        file_system.save(rel)
        return cdem_obj
    elif event._type == "DataExfiltration":
        # HMI data back to the attacker
        cdem_obj = base.Data(
            name="Sensor data", data_type="File",
            description="One week's worth of sensor data files")
        file_system.save(cdem_obj)
        print(
            f'LOG: New Object ({cdem_obj._type}) {cdem_obj.name}')
        return cdem_obj
    elif event._type == "ManipulationAttack":
        cdem_obj = base.Manipulate(
            description="HMI no longer reporting correct data from sensors")
        file_system.save(cdem_obj)
        print(
            f'LOG: New Object ({cdem_obj._type}) {cdem_obj.description}')
        return None


# Wait for attacks...
HOST = '127.0.0.1'
PORT = 65432
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen()
while 1:
    conn, addr = s.accept()
    data = json.loads(str(conn.recv(1024), "utf-8"))
    action = base.load_cyberdem_object(data)
    time.sleep(2)
    print(f'\nRECEIVED INBOUND: {addr[0]}:{addr[1]} TO {action.id}')
    time.sleep(2)
    response = respond(action)
    if response:
        message = response._serialize()
    else:
        message = "RECEIVED"
    conn.sendall(bytes(json.dumps(message), "utf-8"))
