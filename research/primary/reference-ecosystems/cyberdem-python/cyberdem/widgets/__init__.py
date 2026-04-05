"""
Various helpful functions for using Cyber DEM

Cyber DEM Python

Copyright 2020 Carnegie Mellon University.

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
and unlimited distribution. Please see Copyright notice for non-US Government
use and distribution.

DM20-0711
"""

from cyberdem.base import *
import ipaddress
import random

def generate_network(
        num_devices, num_users, filesystem, purpose='enterprise',
        heterogeneity=0, network='192.168.0.0/16'):
    """Create a network of a given size and purpose.

    Given basic parameters, create cyber Objects such as devices, network
    links, software, accounts, and their relationships to each other.

    :param num_devices: total number of workstations, routers, printers, etc.
    :type num_devices: int, required
    :param num_users: total number of users on the network; affects the number
        of accounts and the amount of data and applications
    :type num_users: int, required
    :param filesystem: where to save the generated assets
    :type filesystem: Cyber DEM FileSystem, required
    :param purpose: general purpose of the network; affects the types of
        devices chosen, network architecture, and balance of user workstations
        to network devices
    :type purpose: string, optional (default='enterprise') choose from
        'enterprise', 'scada', 'backbone'
    :param heterogeneity: variety of applications and operating systems on the
        network; zero is completely homogeneous (for example, an all Windows
        network), five is as much variety as possible given the purpose of the
        network
    :type heterogeneity: int, optional (default=0) chose from 0-5
    :param network: the network address range to use
    :type network: string, optional (default 192.168.0.0/16)

    :Example:
        >>> from cyberdem.widgets import generate_network
        >>> from cyberdem.filesystem import FileSystem
        >>> fs = FileSystem('./test-fs')
        >>> generate_network(10, 10, fs)
    """

    purposes = ['enterprise', 'scada', 'backbone']

    # Check inputs
    if not isinstance(num_devices, int):
        raise TypeError(f"num_devices: {num_devices} must be an integer")
    if num_devices == 0:
        raise ValueError(f"num_devices cannot be zero")
    if not isinstance(num_users, int):
        raise TypeError(f"num_users: {num_users} must be an integer")
    if num_users == 0:
        raise ValueError(f"num_users cannot be zero")
    if purpose not in purposes:
        raise ValueError(
            f"{purpose} is not an acceptable value for purpose. Choose from "
            f"{', '.join(purposes)}")
    if not isinstance(heterogeneity, int):
        raise TypeError(
            f"heterogeneity: {heterogeneity} must be an integer 0-5")
    if heterogeneity not in range(0,6):
        raise ValueError(
            f"heterogeneity: {heterogeneity} must be an integer 0-5")

    # Ratio of device types based on the network purpose. Device types come
    # from the DeviceType enumeration, ratios are educated guesses
    device_ratios = {
        'enterprise': {
            'Generic': .9,
            'Monitoring': .01,
            'Networking': .05,
            'Printer': .01,
            'Scanner': .01,
            'Storage': .02
            },
        'scada': {
            'Controller': .4,
            'Generic': .03,
            'HMI': .02,
            'Networking': .04,
            'Sensor': .5
            },
        'backbone': {
            'Generic': .05,
            'Networking': .9,
            'Monitoring': .05
            }
        }

    # Calculate the number of each type of device the network should have
    device_numbers = {}
    for k, v in sorted(device_ratios[purpose].items(), key=lambda i: i[1]):
        num_of_this_type = int(v * num_devices)
        if num_of_this_type == 0:
            num_of_this_type =1
        device_numbers[k] = num_of_this_type
    total_devices = sum([device_numbers[v] for v in device_numbers])
    if total_devices < num_devices:
        device_numbers[k] += num_devices - total_devices
    elif total_devices > num_devices:
        device_numbers[k] -= total_devices - num_devices

    # Calculate the IP blocks
    if purpose == 'scada':
        num_blocks = 5 * device_numbers['Networking']
        num_ints = 5
    elif purpose == 'backbone':
        num_blocks = 3 * device_numbers['Networking']
        num_ints = 3
    else:
        num_blocks = 4 * device_numbers['Networking']
        num_ints = 4
    ip_range = ipaddress.ip_network(network)
    subnets = list(ip_range.subnets(new_prefix=24))[:num_blocks]
    addresses_used = {str(i) : 1 for i in subnets}  # last used ip address

    # Create num_devices devices
    for d in device_numbers:
        i = 1  # counting of devices of certain type
        s = 0  # counting the subnets used
        while i <= device_numbers[d]:
            device = Device(
                name=f'{d} Device {i}',
                description=f'Randomly generated {d} device',
                device_types=[d])
            if d == 'Networking':
                net_ints = []
                while len(net_ints) < num_ints:
                    interface = [f"eth{len(net_ints)}", str(subnets[s][1])]
                    net_ints.append(interface)
                    s += 1
                device.network_interfaces = net_ints
            else:
                ipaddr = subnets[s][addresses_used[str(subnets[s])]+1]
                device.network_interfaces = [["eth0", str(ipaddr)]]
                addresses_used[str(subnets[s])] += 1
                s += 1
                if s >= len(subnets):
                    s = 0
            filesystem.save(device)
            i += 1

    # Create NetworkLink objects
    for subnet in addresses_used:
        subnetwork = ipaddress.ip_network(subnet)
        net_link = NetworkLink(
            name=subnet, is_logical=True)
        net_ints = []
        query = "SELECT id,network_interfaces,device_types FROM Device"
        _, resp = filesystem.query(query)
        for device in resp:
            for interface in device[1]:
                if ipaddress.ip_address(interface[1]) in subnetwork:
                    net_ints.append(interface)
                    filesystem.save(Relationship(device[0], net_link.id))
        net_link.network_interfaces = net_ints
        filesystem.save(net_link)

    # Add users; under the current (Mar 2021) draft of Cyber DEM, there isn't
    # a "user account" object, so using "Persona" object for now
    i = 1
    while i <= num_users:
        persona = Persona(
            name=f'User {i}', description=f'Randomly generated user persona')
        filesystem.save(persona)
        i += 1

    # Add Operating Systems
    # mapping operating systems available by device type (not in Cyber DEM)
    os_to_device = {
        'Controller': [
            'Android',
            'BSDUnix',
            'Firmware',
            'GNUUnix',
            'MicrosoftDOS',
            'MicrosoftWindows',
            ],
        'Generic': [
            'Android',
            'AppleiOS',
            'AppleMacOS',
            'BSDUnix',
            'DECHP_UX',
            'DECVMS',
            'GNUUnix',
            'LinuxRedHat',
            'MicrosoftWindows',
            'Ubuntu'
            ],
        'HMI': [
            'Android',
            'BSDUnix',
            'GNUUnix',
            'LinuxRedHat',
            'MicrosoftWindows',
            'OpenSolaris',
            'Ubuntu'
            ],
        'Monitoring': [
            'BSDUnix',
            'GNUUnix',
            'LinuxRedHat',
            'MicrosoftWindows',
            'Ubuntu'
            ],
        'Networking': [
            'BSDUnix',
            'CiscoIOS',
            'GNUUnix',
            'Ubuntu'
            ],
        'Printer': [
            'Android',
            'BSDUnix',
            'Firmware',
            'GNUUnix',
            ],
        'Scanner': [
            'Android',
            'BSDUnix',
            'Firmware',
            'GNUUnix',
            ],
        'Sensor': [
            'Android',
            'BSDUnix',
            'Firmware',
            'GNUUnix',
            'MicrosoftDOS',
            ],
        'Storage': [
            'Android',
            'BSDUnix',
            'DECHP_UX',
            'GNUUnix',
            'LinuxRedHat',
            'MicrosoftWindows',
            'OpenSolaris',
            'Ubuntu'
            ]
    }
    # get the variety of OSes available based on the heterogeniety
    varieties = {}
    for dt in device_numbers:
        if heterogeneity == 0:
            num_oses = 1
        else:
            num_oses = int(heterogeneity * (len(os_to_device[dt]) / 5))
        if len(os_to_device[dt]) > num_oses:
            varieties[dt] = {
                os : 0 for os in random.sample(os_to_device[dt], num_oses)}
        else:
            varieties[dt] = {os : 0 for os in os_to_device[dt]}
    for device in resp:
        os = random.choice(list(varieties[device[2][0]].keys()))
        if varieties[device[2][0]][os] == 0:
            cd_os = OperatingSystem(os_type=os, name=os)
            filesystem.save(cd_os)
            for k in varieties:
                for i in varieties[k]:
                    if i == os:
                        varieties[k][i] = cd_os.id
        filesystem.save(
            Relationship(varieties[device[2][0]][os], device[0], 'ResidesOn'))

    # TODO add Software (Applications)

    # TODO add Data

def network_summary(
        filesystem, count_only=False, top_N=None, ignore=[], pprint=False):
    """A summary count of CyberObjects in the FileSystem
    
    :param filesystem: where the CyberObjects are stored
    :type filesystem: :class:`~cyberdem.filesystem.FileSystem`, required
    :param count_only: if true, provides only a high level count of CyberObjects
    :type count_only: boolean, optional (default=false)
    :param top_N: only show the top N results of each object type/name
    :type top_N: integer, optional
    :param ignore: don't include specified CyberObject types
    :type ignore: list, optional
    :param pprint: line and tab delimited print out for quick command line
        reading
    :type pprint: boolean, optional (default=false)

    :Example:
        >>> from cyberdem.widgets import network_summary
        >>> from cyberdem.filesystem import FileSystem
        >>> fs = FileSystem('./test-fs')
        >>> summary = network_summary(fs, top_N=5, pprint=True)
        >>> print(summary)
    """

    counts = {
        'Applications': 'Application',
        'Data': 'Data',
        'Devices': 'Device',
        'Networks': 'Network',
        'Network Links': 'NetworkLink',
        'Operating systems': 'OperatingSystem',
        'Personas': 'Persona',
        'Services': 'Service',
        'Systems': 'System'
        }
    type_breakdown = {
        'Networks': ',mask',
        'Network Links': '',
        'Devices': ',device_type',
        'Services': ',service_type',
        'Operating systems': ',os_type',
        'Applications': ',name',
        'Personas': '',
        'Data': ',data_type',
        'Systems': ',system_type'
        }

    # Check the ignore variable
    for var in ignore:
        if var not in filesystem.obj_types:
            raise ValueError('ERROR!!!')
        else:
            counts_key = [k for k in counts if counts[k] == var][0]
            del counts[counts_key]
            del type_breakdown[counts_key]

    for obj in counts:
        query = f"SELECT id{type_breakdown[obj]} FROM {counts[obj]}"
        _, results = filesystem.query(query)
        counts[obj] = len(results)
        type_breakdown[obj] = {}
        for r in results:
            try:
                obj_type = r[1]
            except IndexError:
                obj_type = None
            if obj_type is not None:
                try:
                    type_breakdown[obj][obj_type] += 1
                except KeyError:
                    type_breakdown[obj][obj_type] = 1

    if count_only:
        data = {'Counts': counts}
    else:
        for t in type_breakdown:
            type_breakdown[t] = sorted(
                type_breakdown[t].items(), key = lambda kv:[-kv[1], kv[0]])
            if top_N is not None:
                allowed = sorted(set(
                    [v[1] for v in type_breakdown[t]]), reverse=True)[:top_N]
                tb = [[k, v] for k, v in type_breakdown[t] if v in allowed]
                type_breakdown[t] = tb
            else:
                # convert tuples from sort to lists (json fail)
                list_of_lists = []
                for tb in type_breakdown[t]:
                    list_of_lists.append(list(tb))
                type_breakdown[t] = list_of_lists
        data = {
            'Counts': counts,
            'Type Summary': type_breakdown}

    if pprint:
        pretty = ''
        for k in data:
            pretty += k.upper() + '\n'
            for obj_type in data[k]:
                if isinstance(data[k][obj_type], int):
                    pretty += f'\t{obj_type}: {data[k][obj_type]}\n'
                else:
                    if len(data[k][obj_type]) == 0:
                        continue
                    pretty += f'\t{obj_type}:\n'
                    for sub_obj in data[k][obj_type]:
                        pretty += f'\t\t{sub_obj[0]}: {sub_obj[1]}\n'
        data = pretty

    return data