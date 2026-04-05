'''
CyberDEM Enumerations Module

CyberDEM Python

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
and unlimited distribution.  Please see Copyright notice for non-US Government
use and distribution.

DM20-0711
'''


class _CyberDEMEnumeration:
    """Super class for all CyberDEM enumerations"""

    _opts = []

    @classmethod
    def _check_prop(cls, value):
        """Checks to see if ``value`` is an allowed enumeration value.

        Compares the given value to the allowed options for the current
        enumeration subclass.

        :param value: user-provided value for the enumeration type
        :type value: required

        :raises ValueError: if the ``value`` is not in the allowed options of
            the enumeration class.

        :Example:
            >>> from cyberdem.enumerations import NetworkProtocolType
            >>> NetworkProtocolType._check_prop('ARP')
        """

        if value.lower() not in [o.lower() for o in cls._opts]:
            raise ValueError(f'"{value}" is not a valid value for {cls.__name__}. Options are {", ".join(cls._opts)}.')
        if value not in cls._opts:
            print(f'Warning: "{value}" is not the same capitalization as {cls.__name__} option.')


class AcknowledgeResponseType(_CyberDEMEnumeration):
    """CyberDEM AcknowledgeResponseType enumeration

    :options: 'AbleToComply', 'UnableToComply'
    """

    _opts = [
        'AbleToComply',
        'UnableToComply',
    ]


class AdminType(_CyberDEMEnumeration):
    """CyberDEM AdminType enumeration

    :options: 'Administration','Assessment','Collection','Configuration',
        'Evaluation','Forensics','Investigation','Operations',
        'Provisioning','Testing'
    """

    _opts = [
        'Administration',
        'Assessment',
        'Collection',
        'Configuration',
        'Evaluation',
        'Forensics',
        'Investigation',
        'Operations',
        'Provisioning',
        'Testing',
    ]


class CyberEventPhaseType(_CyberDEMEnumeration):
    """CyberDEM CyberEventPhaseType enumeration

    :options: 'Start', 'Suspend', 'Continue', 'ContinueWithChanges', 'End', 'Cancel'
    """

    _opts = [
        'Start',
        'Suspend',
        'Continue',
        'ContinueWithChanges',
        'End',
        'Cancel',
    ]


class DataLinkProtocolType(_CyberDEMEnumeration):
    """CyberDEM DataLinkProtocolType enumeration

    :options: 'Ethernet', 'WiFi', 'ATM', 'LocalTalk', 'PPP',
        'TokenRing', 'VLAN', 'Bluetooth', '1553Bus'
    """

    _opts = [
        'Ethernet',
        'WiFi',
        'ATM',
        'LocalTalk',
        'PPP',
        'TokenRing',
        'VLAN',
        'Bluetooth',
        '1553Bus',
    ]


class DataStatusType(_CyberDEMEnumeration):
    """CyberDEM DataStatusType enumeration

    :options: 'Intact', 'Compromised', 'Corrupted', 'Manipulated', 'NonDecryptable',
        'Erased'
    """

    _opts = [
        'Intact',
        'Compromised',
        'Corrupted',
        'Manipulated',
        'NonDecryptable',
        'Erased',
    ]


class DataType(_CyberDEMEnumeration):
    """CyberDEM DataType enumeration

    :options: 'File','Code', 'Credentials', 'Communications','SystemConfiguration'
    """

    _opts = [
        'File',
        'Code',
        'Credentials',
        'Communications',
        'SystemConfiguration',
    ]


class DeviceType(_CyberDEMEnumeration):
    """CyberDEM DeviceType enumeration

    :options: 'Generic', 'Networking', 'ComputerNode', 'PortableComputer', 'Controller',
        'Storage', 'Sensor', 'Printer', 'Scanner', 'Communications', 'HMI', 'Monitoring',
        'IoT', 'Security',
    """

    _opts = [
        'Generic',
        'Networking',
        'ComputerNode',
        'PortableComputer',
        'Controller',
        'Storage',
        'Sensor',
        'Printer',
        'Scanner',
        'Communications',
        'HMI',
        'Monitoring',
        'IoT',
        'Security',
    ]

    @classmethod
    def _check_prop(cls, values):
        """Checks to see if each value in ``values`` is an allowed enumeration value.

        Overrides the :func:`~_CyberDEMEnumeration._check_prop` function from
        the super :class:`_CyberDEMEnumeration`

        Compares the given values to the allowed options for the current
        enumeration class (sub-class to :class:`_CyberDEMEnumeration`).

        :param values: user-provided list of values for the enumeration type
        :type values: list, required

        :raises ValueError: if the values in ``values`` are not in the allowed
            options.

        :Example:
            >>> from cyberdem.enumerations import DeviceType
            >>> DeviceType._check_prop(['HMI','Sensor'])
        """
        if not isinstance(values, list):
            raise ValueError(f'"values" should be a list of {cls.__name__}')
        for t in values:
            if t.lower() not in [o.lower() for o in cls._opts]:
                raise ValueError(f'"{t}" is not a valid value for {cls.__name__}. Options are {", ".join(cls._opts)}.')
            if t not in cls._opts:
                print(f'Warning: "{t}" is not the same capitalization as {cls.__name__} option.')


class EncryptionType(_CyberDEMEnumeration):
    """CyberDEM EncryptionType enumeration

    :options: 'NotEncrypted', 'DES', 'TripleDES', 'RSA', 'AES', 'TwoFish', 'SHA'
    """

    _opts = [
        'NotEncrypted',
        'DES',
        'TripleDES',
        'RSA',
        'AES',
        'TwoFish',
        'SHA',
    ]


class HardwareDamageType(_CyberDEMEnumeration):
    """CyberDEM HardwareDamageType enumeration

    :options: 'BootLoop', 'PhysicalDestruction', 'HardDriveErased'
    """

    _opts = [
        'BootLoop',
        'PhysicalDestruction',
        'HardDriveErased',
    ]


class HardwareDegradeType(_CyberDEMEnumeration):
    """CyberDEM HardwareDegradeType enumeration

    :options: 'Keyboard', 'Mouse', 'Display', 'Sound'
    """

    _opts = [
        'Keyboard',
        'Mouse',
        'Display',
        'Sound',
    ]


class LoadRateType(_CyberDEMEnumeration):
    """CyberDEM LoadRateType enumeration

    :options: 'Upload', 'Download'
    """

    _opts = [
        'Upload',
        'Download',
    ]


class ManipulationType(_CyberDEMEnumeration):
    """CyberDEM ManipulationType enumeration

    :options: 'Packet', 'File', 'Database'
    """

    _opts = [
        'Packet',
        'File',
        'Database',
    ]


class MessageType(_CyberDEMEnumeration):
    """CyberDEM MessageType enumeration

    :options: 'Email', 'Chat', 'Text', 'SocialMedia'
    """

    _opts = [
        'Email',
        'Chat',
        'Text',
        'SocialMedia',
    ]


class NetworkProtocolType(_CyberDEMEnumeration):
    """CyberDEM NetworkProtocolType enumeration

    :options: 'InternetProtocol', 'NAT', 'ICMP', 'ARP', 'RIP', 'OSPF', 'IPsec'
    """

    _opts = [
        'InternetProtocol',
        'NAT',
        'ICMP',
        'ARP',
        'RIP',
        'OSPF',
        'IPsec',
    ]


class OperatingSystemType(_CyberDEMEnumeration):
    """CyberDEM OperatingSystemType enumeration

    :options: 'MicrosoftDOS', 'MicrosoftWindows', 'AppleMacOS', 'DECVMS',
        'IBMOS 2', 'Android', 'AppleiOS', 'CiscoIOS', 'Firmware', 'UNIX-Linux'
    """

    _opts = [
        'MicrosoftDOS',
        'MicrosoftWindows',
        'AppleMacOS',
        'DECVMS',
        'IBMOS 2',
        'Android',
        'AppleiOS',
        'CiscoIOS',
        'Firmware',
        'UNIX-Linux',
    ]


class PacketManipulationType(_CyberDEMEnumeration):
    """CyberDEM PacketManipulationType enumeration

    :options: 'Duplication', 'Corruption', 'Redordering', 'Dropped'
    """

    _opts = [
        'Duplication',
        'Corruption',
        'Redordering',
        'Dropped',
    ]


class PhysicalLayerType(_CyberDEMEnumeration):
    """CyberDEM PhysicalLayerType enumeration

    :options: 'Wired', 'Wireless'
    """

    _opts = [
        'Wired',
        'Wireless',
    ]


class ReconType(_CyberDEMEnumeration):
    """CyberDEM ReconType enumeration

    :options:
        'AccountDiscovery', 'AdMalware', 'AntivirusTrojan',
        'ApplicationWindowDiscovery', 'ARPScan', 'BannerGrabbing',
        'BounceScan', 'BrowserBookmarkDiscovery', 'CloudInfrastructureDiscovery',
        'CloudServiceDashboard', 'CloudServiceDiscovery', 'Compliance', 'CSRF',
        'DatabaseInjection', 'DatabaseStructure', 'DBManufactureVersion', 'Device',
        'DNS', 'Domain', 'DomainTrustDiscovery', 'FileAndDirectoryDiscovery',
        'FINScan', 'FTP', 'HTTP', 'IdleScan', 'IGMP', 'InputValidation', 'IP',
        'LDAPScan', 'NetBiosScan', 'NetworkMap', 'NetworkServiceScanning',
        'NetworkShareDiscovery', 'NetworkSniffing', 'NTP', 'NULLScan', 'OSScan',
        'PasswordPolicyDiscovery', 'PatchHistory', 'PeripheralDeviceDiscovery',
        'PermissionGroupsDiscovery', 'Ping', 'PingScan', 'PortScan', 'PortSweep',
        'PPP', 'ProcessDiscovery', 'QueryRegistry', 'RARP', 'Remote SystemDiscovery',
        'Rootkit', 'RPCScan', 'Service', 'SLIP', 'SMTP', 'SNMPSweep',
        'SoftwareDiscover', 'SYNScan', 'SystemlnformationDiscovery',
        'SystemNetworkConfigurationDiscovery', 'SystemNetworkConnectionsDiscovery',
        'SystemOwnerUserDiscovery', 'SystemServiceDiscovery', 'SystemTimeDiscovery',
        'TCPConnect', 'TraceRoute', 'UNIX-Linux', 'VirtualizationSandboxEvasion',
        'Vulnerability', 'WebCrawler', 'Windows', 'WirelessActive', 'WirelessPassive',
        'XMASScan', 'XSS'
    """

    _opts = [
        'AccountDiscovery',
        'AdMalware',
        'AntivirusTrojan',
        'ApplicationWindowDiscovery',
        'ARPScan',
        'BannerGrabbing',
        'BounceScan',
        'BrowserBookmarkDiscovery',
        'CloudInfrastructureDiscovery',
        'CloudServiceDashboard',
        'CloudServiceDiscovery',
        'Compliance',
        'CSRF',
        'DatabaseInjection',
        'DatabaseStructure',
        'DBManufactureVersion',
        'Device',
        'DNS',
        'Domain',
        'DomainTrustDiscovery',
        'FileAndDirectoryDiscovery',
        'FINScan',
        'FTP',
        'HTTP',
        'IdleScan',
        'IGMP',
        'InputValidation',
        'IP',
        'LDAPScan',
        'NetBiosScan',
        'NetworkMap',
        'NetworkServiceScanning',
        'NetworkShareDiscovery',
        'NetworkSniffing',
        'NTP',
        'NULLScan',
        'OSScan',
        'PasswordPolicyDiscovery',
        'PatchHistory',
        'PeripheralDeviceDiscovery',
        'PermissionGroupsDiscovery',
        'Ping',
        'PingScan',
        'PortScan',
        'PortSweep',
        'PPP',
        'ProcessDiscovery',
        'QueryRegistry',
        'RARP',
        'Remote SystemDiscovery',
        'Rootkit',
        'RPCScan',
        'Service',
        'SLIP',
        'SMTP',
        'SNMPSweep',
        'SoftwareDiscover',
        'SYNScan',
        'SystemlnformationDiscovery',
        'SystemNetworkConfigurationDiscovery',
        'SystemNetworkConnectionsDiscovery',
        'SystemOwnerUserDiscovery',
        'SystemServiceDiscovery',
        'SystemTimeDiscovery',
        'TCPConnect',
        'TraceRoute',
        'UNIX-Linux',
        'VirtualizationSandboxEvasion',
        'Vulnerability',
        'WebCrawler',
        'Windows',
        'WirelessActive',
        'WirelessPassive',
        'XMASScan',
        'XSS',
    ]


class RelationshipType(_CyberDEMEnumeration):
    """CyberDEM RelationshipType enumeration

    :options: 'Administers', 'AdministeredBy', 'ComponentOf', 'HasComponent',
        'ContainedIn', 'Contains', 'ProvidedBy', 'Provides', 'ResidesOn',
        'HasResident'
    """

    _opts = [
        'Administers',
        'AdministeredBy',
        'ComponentOf',
        'HasComponent',
        'ContainedIn',
        'Contains',
        'ProvidedBy',
        'Provides',
        'ResidesOn',
        'HasResident',
    ]


class SensitivityType(_CyberDEMEnumeration):
    """CyberDEM SensitivityType enumeration

    :options: 'Unclassified', 'Confidential', 'FOUO', 'Secret', 'SecretNoForn',
        'TS', 'TS_SCI', 'NATORestricted', 'NATOConfidential', 'NATOSecret',
        'CosmicTopSecret', 'FVEYProprietary', 'Proprietary', 'PII', 'HIPAA',
        'GDPR', 'Public'
    """

    _opts = [
        'Unclassified',
        'Confidential',
        'FOUO',
        'Secret',
        'SecretNoForn',
        'TS',
        'TS_SCI',
        'NATORestricted',
        'NATOConfidential',
        'NATOSecret',
        'CosmicTopSecret',
        'FVEYProprietary',
        'Proprietary',
        'PII',
        'HIPAA',
        'GDPR',
        'Public',
    ]


class ServiceType(_CyberDEMEnumeration):
    """CyberDEM ServiceType enumeration

    :options: 'DNS', 'Email', 'Web', 'Database', 'File', 'Chat', 'Forum',
        'SocialMedia', 'Containerization', 'Virtualization', 'NetworkTime'
    """

    _opts = [
        'DNS',
        'Email',
        'Web',
        'Database',
        'File',
        'Chat',
        'Forum',
        'SocialMedia',
        'Containerization',
        'Virtualization',
        'NetworkTime',
    ]


class SystemType(_CyberDEMEnumeration):
    """CyberDEM SystemType enumeration

    :options: 'C2', 'Generic', 'ICS', 'SCADA'
    """

    _opts = [
        'Generic',
        'SCADA',
        'C2',
        'ICS',
    ]
