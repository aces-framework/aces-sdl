"""
Object/Event classes for Cyber DEM

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


from datetime import datetime, timedelta
from cyberdem.enumerations import *
import uuid
import inspect
import sys


class _CyberDEMBase:
    """Superclass for all Cyber DEM Objects and Events

    Will create an appropriate ``id`` if one is not given.

    :param id: A federation unique identifier string formatted UUIDv4
    :type id: string, optional

    :raises ValueError: if a given ``id`` is not a valid string representation
        of a UUIDv4
    """

    _type = None

    def __init__(self, id=None, **kwargs):
        if id is None:
            id = str(uuid.uuid4())
        if len(kwargs) > 0:
            raise ValueError(f'Invalid attribute(s): {", ".join([k for k in kwargs.keys()])}')
        self.id = id

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        try:
            uuid.UUID(value)
        except ValueError:
            raise ValueError(f'"{value}"" is not a valid value for id. Must be a UUIDv4.')
        self._id = value

    def __str__(self):
        string = self._type + "("
        for attr in self.__dict__:
            if attr.startswith('_'):
                string += '\n    ' + attr[1:] + ': ' + str(self.__dict__[attr])
            else:
                string += '\n    ' + attr + ': ' + str(self.__dict__[attr])
        string += "\n)"
        return string

    def __repr__(self):
        return str(self.__dict__)

    def _serialize(self):
        serialized = {}
        for key, value in self.__dict__.items():
            if isinstance(value, (datetime, timedelta)):
                s_value = str(value)
            else:
                s_value = value
            if key.startswith('_'):
                serialized[key[1:]] = s_value
            else:
                serialized[key] = s_value
        serialized['_type'] = self._type
        return serialized


def load_cyberdem_object(instance_dict):
    """Given a dictionary representing a Cyber DEM object or event, return an
        instance of that object/event.

    :param instance_dict: representation of a Cyber DEM object or event
    :type instance_dict: dict, required

    :Example:
        >>> from cyberdem import base
        >>> foo = {"_type": "Application", "name": "foo", "description": "bar"}
        >>> bar = base.load_cyberdem_object(foo)
        >>> type(bar)
        <class 'cyberdem.base.Application'>
    """

    # Get all of the classes into a dictionary so they can be called
    obj_types = {}
    for _, test_obj in inspect.getmembers(sys.modules[__name__], inspect.isclass):
        if test_obj.__module__ == 'cyberdem.base':
            if test_obj._type:
                obj_types[test_obj._type] = test_obj

    obj_type = instance_dict['_type']
    del instance_dict['_type']
    obj = obj_types[obj_type](**instance_dict)  # instantiate the object

    return obj


# Second level Cyber DEM objects
class _CyberObject(_CyberDEMBase):
    """Superclass for all CyberDEM CyberObjects

    CyberObjects are persistent objects on a network or other cyber
    infrastructure.

    Inherits :class:`_CyberDEMBase`. Optionally sets the name and/or
    description parameters for any CyberObject subclass.

    :param name: The identifier for use in user interfaces, visualization, analysis, etc
    :type name: string, optional
    :param description: A short description of the object
    :type description: string, optional
    :param kwargs: Arguments to pass to the :class:`_CyberDEMBase` class
    :type kwargs: dictionary, optional
    """

    def __init__(self, name=None, description=None, **kwargs):
        super().__init__(**kwargs)
        if name:
            self.name = name
        if description:
            self.description = description

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{type(value)} is not a valid type for name. Must be string.')
        self._name = value

    @name.deleter
    def name(self):
        del self._name

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{type(value)} is not a valid type for description. Must be string.')
        self._description = value

    @description.deleter
    def description(self):
        del self._description


class _CyberEvent(_CyberDEMBase):
    """Superclass for all CyberDEM CyberEvents

    CyberEvents are non-persistent cyber events, as opposed to persistent
    CyberObjects.

    Inherits :class:`_CyberDEMBase`. Optionally sets the description, event_time,
    target_ids, cyber event phase, duration, actor_ids, and/or source_ids
    parameters for any CyberEvent subclass.

    :param description: A human readable description of the event
    :type description: string, optional
    :param event_time: Time at which the event started
    :type event_time: datetime.datetime, optional
    :param target_ids: One or more IDs identifying the CyberObject(s) targeted in
        the event
    :type target_ids: list, optional
    :param target_modifiers: mapping of target characteristics to values
    :type target_modifiers: dictionary, optional
    :param phase: The cyber event phase of the event
    :type phase: value from :class:`~cyberdem.enumerations.CyberEventPhaseType`
        enumeration, optional
    :param duration: Length of time the event lasted
    :type duration: datetime.timedelta, optional
    :param actor_ids: Time ordered list of IDs of the perpetrators involved in
        this Cyber Event
    :type actor_ids: list, optional
    :param source_ids: Time ordered list of IDs of the simulations that this
        Cyber Event came from.
    :type source_ids: list, optional
    :param payload: Contains the details of the event itself or the message
        after the event, as decided by the federation agreement
    :type payload: blob, optional
    :param request_acknowledgement: True if the receiver should send an
        acknowledgement back to the sender
    :type request_acknowledgement: boolean, optional
    :param kwargs: Arguments to pass to the :class:`_CyberDEMBase` class
    :type kwargs: dictionary, optional
    """

    def __init__(
        self,
        description=None,
        event_time=None,
        target_ids=None,
        target_modifiers=None,
        phase=None,
        duration=None,
        actor_ids=None,
        source_ids=None,
        payload=None,
        request_acknowledgement=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if description:
            self.description = description
        if event_time:
            self.event_time = event_time
        if target_ids:
            self.target_ids = target_ids
        if target_modifiers:
            self.target_modifiers = target_modifiers
        if phase:
            self.phase = phase
        if duration:
            self.duration = duration
        if actor_ids:
            self.actor_ids = actor_ids
        if source_ids:
            self.source_ids = source_ids
        if payload:
            self.payload = payload
        if request_acknowledgement:
            self.request_acknowledgement = request_acknowledgement

    @property
    def event_time(self):
        return self._event_time

    @event_time.setter
    def event_time(self, value):
        if not isinstance(value, datetime):
            raise TypeError(f'{type(value)} is not a valid type for event_time. Must be datetime.')
        self._event_time = value

    @event_time.deleter
    def event_time(self):
        del self._event_time

    @property
    def target_ids(self):
        return self._target_ids

    @target_ids.setter
    def target_ids(self, value):
        if not isinstance(value, list):
            raise TypeError(f'{type(value)} is not a valid type for target_ids. Must be a list of IDs.')
        for v in value:
            try:
                uuid.UUID(v)
            except ValueError:
                raise ValueError(f'"{v}" is not a valid value in target_ids. Must be an ID.')
        self._target_ids = value

    @target_ids.deleter
    def target_ids(self):
        del self._target_ids

    @property
    def target_modifiers(self):
        return self._target_modifiers

    @target_modifiers.setter
    def target_modifiers(self, value):
        if not isinstance(value, dict):
            raise TypeError(f'{type(value)} is not a valid type for target_modifiers. Must be a dictionary')
        self._target_modifiers = value

    @target_modifiers.deleter
    def target_modifiers(self):
        del self._target_modifiers

    @property
    def phase(self):
        return self._phase

    @phase.setter
    def phase(self, value):
        CyberEventPhaseType()._check_prop(value)
        self._phase = value

    @phase.deleter
    def phase(self):
        del self._phase

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        if not isinstance(value, timedelta):
            raise TypeError(f'{type(value)} is not a valid type for duration. Must be timedelta.')
        self._duration = value

    @duration.deleter
    def duration(self):
        del self._duration

    @property
    def actor_ids(self):
        return self._actor_ids

    @actor_ids.setter
    def actor_ids(self, value):
        if not isinstance(value, list):
            raise TypeError(f'{type(value)} is not a valid type for actor_ids. Must be list of IDs.')
        for v in value:
            try:
                uuid.UUID(v)
            except ValueError:
                raise ValueError(f'"{v}" is not a valid value in actor_ids. Must be an ID.')
        self._actor_ids = value

    @actor_ids.deleter
    def actor_ids(self):
        del self._actor_ids

    @property
    def source_ids(self):
        return self._source_ids

    @source_ids.setter
    def source_ids(self, value):
        if not isinstance(value, list):
            raise TypeError(f'{type(value)} is not a valid type for source_ids. Must be list of IDs.')
        for v in value:
            try:
                uuid.UUID(v)
            except ValueError:
                raise ValueError(f'"{v}" is not a valid value in source_ids. Must be an ID.')
        self._source_ids = value

    @source_ids.deleter
    def source_ids(self):
        del self._source_ids

    @property
    def payload(self):
        return self._payload

    @payload.setter
    def payload(self, value):
        # TODO handle blob type for payload (base64 encoded string?)
        # if not isinstance(value, ...):
        #     raise TypeError(f'{type(value)} is not a valid type for payload. Must be ...')
        self._payload = value

    @payload.deleter
    def payload(self):
        del self._payload

    @property
    def request_acknowledgement(self):
        return self._request_acknowledgement

    @request_acknowledgement.setter
    def request_acknowledgement(self, value):
        if not isinstance(value, bool):
            raise TypeError(f'{type(value)} is not a valid type for request_acknowledgement. Must be a boolean.')
        self._request_acknowledgement = value

    @request_acknowledgement.deleter
    def request_acknowledgement(self):
        del self._request_acknowledgement


# Third level Cyber DEM CyberEvents
class _CyberEffect(_CyberEvent):
    """Passive superclass for all Cyber DEM CyberEffects.

    Inherits :class:`_CyberEvent`. No additional attributes.
    """

    pass


class _CyberAction(_CyberEvent):
    """Passive superclass for all Cyber DEM CyberActions.

    Inherits :class:`_CyberEvent`. Included for completeness of the Cyber DEM
    standard.
    """

    pass


class CyberAcknowledge(_CyberEvent):
    """
    Cyber Acknowledge represents a response to a Cyber Event that has requested
    an acknowledgement.

    Inherits :class:`_CyberEvent`.

    :param related_event_id: ID of the Cyber Event being acknowledged
    :type related_event_id: string, optional
    :param acknowledge_response: The response to the related event being acknowledged
    :type acknowledge_response: value from
        :class:`~cyberdem.enumerations.AcknowledgeResponseType` enumeration, optional
    :param kwargs: Arguments to pass to the :class:`_CyberEvent` class
    :type kwargs: dictionary, optional

    :Example: TODO
    """

    _type = "CyberAcknowledge"

    def __init__(self, related_event_id=None, acknowledge_response=None, **kwargs):
        super().__init__(**kwargs)
        if related_event_id:
            self.related_event_id = related_event_id
        if acknowledge_response:
            self.acknowledge_response = acknowledge_response

    @property
    def related_event_id(self):
        return self._related_event_id

    @related_event_id.setter
    def related_event_id(self, value):
        try:
            uuid.UUID(value)
        except ValueError:
            raise ValueError(f'"{value}" is not a valid value in related_event_id. Must be an ID.')
        self._related_event_id = value

    @related_event_id.deleter
    def related_event_id(self):
        del self._related_event_id

    @property
    def acknowledge_response(self):
        return self._acknowledge_response

    @acknowledge_response.setter
    def acknowledge_response(self, value):
        AcknowledgeResponseType._check_prop(value)
        self._acknowledge_response = value

    @acknowledge_response.deleter
    def acknowledge_response(self):
        del self._acknowledge_response


class CyberOrder(_CyberEvent):
    """
    Cyber Order captures cyberspace related command and control orders/directives.
    Cyber Order is an abstract class intended as an organizational construct.
    The commander will need a persona to be represented in the Actor ID.
    If the order is directed at live subordinates, they will need to have personas to
    be the targets of the order. The content of the orders is represented
    in the Target Modifiers.

    Inherits :class:`_CyberEvent`.

    :param kwargs: Arguments to pass to the :class:`_CyberEvent` class
    :type kwargs: dictionary, optional

    :Example: TODO
    """

    _type = "CyberOrder"


# Third level Cyber DEM CyberObjects
class Application(_CyberObject):
    """Representation of an Application object.

    Inherits :class:`_CyberObject`.

    :param version: Vendor or developer assigned version.
    :type version: string, optional
    :param company: Developer/Producer name.
    :type company: string, optional
    :param kwargs: Arguments to pass to the :class:`_CyberObject` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Application
        >>> kwargs = {
        ...    'version': '2.4.2',
        ...    'name': 'PfSense',
        ...    'description': 'PfSense Firewall'
        ...    }
        >>> my_app = Application(**kwargs)
    """

    _type = "Application"

    def __init__(self, version=None, company=None, **kwargs):
        super().__init__(**kwargs)
        if version:
            self.version = version
        if company:
            self.company = company

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{type(value)} is not a valid type for version. Must be string.')
        self._version = value

    @version.deleter
    def version(self):
        del self._version

    @property
    def company(self):
        return self._company

    @company.setter
    def company(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{type(value)} is not a valid type for company. Must be string.')
        self._company = value

    @company.deleter
    def company(self):
        del self._company


class Data(_CyberObject):
    """Representation of a Data object

    Inherits :class:`_CyberObject`.

    :param sensitivity: [desc]
    :type sensitivity: value from
        :class:`~cyberdem.enumerations.SensitivityType` enumeration, optional
    :param data_type: [desc]
    :type data_type: value from
        :class:`~cyberdem.enumerations.DataType` enumeration, optional
    :param encrypted: [desc]
    :type encrypted: value from
        :class:`~cyberdem.enumerations.EncryptionType` enumeration, optional
    :param status: [desc]
    :type status: value from
        :class:`~cyberdem.enumerations.DataStatusType` enumeration, optional
    :param confidentiality: [desc]
    :type confidentiality: float, optional
    :param kwargs: Arguments to pass to the :class:`_CyberObject` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Data
        >>> kwargs = {
        ...    'sensitivity': 'FOUO',
        ...    'data_type': 'File',
        ...    'confidentiality': 0.6,
        ...    'name': 'Foo File',
        ...    'description': 'Foobarred file'
        ...    }
        >>> my_data = Data(**kwargs)
    """

    _type = "Data"

    def __init__(self, sensitivity=None, data_type=None, encrypted=None, status=None, confidentiality=None, **kwargs):
        super().__init__(**kwargs)
        if sensitivity:
            self.sensitivity = sensitivity
        if data_type:
            self.data_type = data_type
        if encrypted:
            self.encrypted = encrypted
        if status:
            self.status = status
        if confidentiality:
            self.confidentiality = confidentiality

    @property
    def sensitivity(self):
        return self._sensitivity

    @sensitivity.setter
    def sensitivity(self, value):
        SensitivityType()._check_prop(value)
        self._sensitivity = value

    @sensitivity.deleter
    def sensitivity(self):
        del self._sensitivity

    @property
    def data_type(self):
        return self._data_type

    @data_type.setter
    def data_type(self, value):
        DataType()._check_prop(value)
        self._data_type = value

    @data_type.deleter
    def data_type(self):
        del self._data_type

    @property
    def encrypted(self):
        return self._encrypted

    @encrypted.setter
    def encrypted(self, value):
        EncryptionType()._check_prop(value)
        self._encrypted = value

    @encrypted.deleter
    def encrypted(self):
        del self._encrypted

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        DataStatusType()._check_prop(value)
        self._status = value

    @status.deleter
    def status(self):
        del self._status

    @property
    def confidentiality(self):
        return self._confidentiality

    @confidentiality.setter
    def confidentiality(self, value):
        if not isinstance(value, float):
            raise TypeError(f'{type(value)} is not a valid type for confidentiality. Must be float.')
        self._confidentiality = value

    @confidentiality.deleter
    def confidentiality(self):
        del self._confidentiality


class Device(_CyberObject):
    """Representation of a Device object.

    Inherits :class:`_CyberObject`.

    :param device_types: Type(s) of device (ex. "Sensor", "Printer")
    :type device_types: list of values from the
        :class:`~cyberdem.enumerations.DeviceType` enumeration, optional
    :param is_virtual: whether the device is a virtual device
    :type is_virtual: boolean, optional
    :param role: [desc]
    :type role: string, optional
    :param device_identifier: [desc]
    :type device_identifier: string, optional
    :param network_interfaces: mapping of interface names to addresses
    :type network_interfaces: list of lists, optional
    :param kwargs: Arguments to pass to the :class:`_CyberObject` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Device
        >>> kwargs = {
        ...    'device_type': ['Generic'],
        ...    'is_virtual': False,
        ...    'device_identifier':\
            '(01)12345678987654(55)120717(55)A12345B(55)4321',
        ...    'name': 'The Server',
        ...    'description': 'Generic server description'
        ...    }
        >>> net_ints = [['eth0','204.105.24.23'], ['eth1','192.168.10.101']]
        >>> my_device = Device(network_interfaces=net_ints, **kwargs)
    """

    _type = "Device"

    def __init__(
        self, device_types=None, is_virtual=None, role=None, device_identifier=None, network_interfaces=None, **kwargs
    ):
        super().__init__(**kwargs)
        if device_types:
            self.device_types = device_types
        if is_virtual:
            self.is_virtual = is_virtual
        if role:
            self.role = role
        if device_identifier:
            self.device_identifier = device_identifier
        if network_interfaces:
            self.network_interfaces = network_interfaces

    @property
    def device_types(self):
        return self._device_types

    @device_types.setter
    def device_types(self, value):
        DeviceType()._check_prop(value)
        self._device_types = value

    @device_types.deleter
    def device_types(self):
        del self._device_types

    @property
    def is_virtual(self):
        return self._is_virtual

    @is_virtual.setter
    def is_virtual(self, value):
        if not isinstance(value, bool):
            raise TypeError(f'{type(value)} is not a valid type for is_virtual. Must be boolean.')
        self._is_virtual = value

    @is_virtual.deleter
    def is_virtual(self):
        del self._is_virtual

    @property
    def role(self):
        return self._role

    @role.setter
    def role(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{type(value)} is not a valid type for role. Must be string.')
        self._role = value

    @role.deleter
    def role(self):
        del self._role

    @property
    def device_identifier(self):
        return self._device_identifier

    @device_identifier.setter
    def device_identifier(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{type(value)} is not a valid type for device_identifier. Must be string.')
        self._device_identifier = value

    @device_identifier.deleter
    def device_identifier(self):
        del self._device_identifier

    @property
    def network_interfaces(self):
        return self._network_interfaces

    @network_interfaces.setter
    def network_interfaces(self, value):
        if not isinstance(value, list):
            raise TypeError(
                f'{type(value)} is not a valid type for network_interface.'
                f'Must be a list of lists. Ex. "[[\'eth0\', \'1.2.3.4\'], '
                f'[...]]"'
            )
        for net_int in value:
            if not isinstance(net_int, list):
                raise TypeError(f'{type(net_int)} for {net_int} must be a list. Ex. "[\'eth0\', \'1.2.3.4\']"')
        self._network_interfaces = value

    @network_interfaces.deleter
    def network_interfaces(self):
        del self._network_interfaces


class Network(_CyberObject):
    """Representation of a Network object.

    Inherits :class:`_CyberObject`.

    :param protocol: protocol used on the network
    :type protocol: value from the
        :class:`~cyberdem.enumerations.NetworkProtocolType` enumeration,
        optional
    :param mask: network mask
    :type mask: string, optional
    :param kwargs: Arguments to pass to the :class:`_CyberObject` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Network
        >>> kwargs = {
        ...    'protocol': 'OSPF',
        ...    'mask': '255.255.255.0',
        ...    'name': 'Network 10',
        ...    'description': 'User network'
        ... }
        >>> my_network = Network(**kwargs)
    """

    _type = "Network"

    def __init__(self, protocol=None, mask=None, **kwargs):
        super().__init__(**kwargs)
        if protocol:
            self.protocol = protocol
        if mask:
            self.mask = mask

    @property
    def protocol(self):
        return self._protocol

    @protocol.setter
    def protocol(self, value):
        NetworkProtocolType()._check_prop(value)
        self._protocol = value

    @protocol.deleter
    def protocol(self):
        del self._protocol

    @property
    def mask(self):
        return self._mask

    @mask.setter
    def mask(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{type(value)} is not a valid type for mask. Must be string.')
        self._mask = value

    @mask.deleter
    def mask(self):
        del self._mask


class NetworkLink(_CyberObject):
    """Representation of a NetworkLink object.

    Inherits :class:`_CyberObject`.

    :param is_logical: the link is logical (rather than physical)
    :type is_logical: boolean, optional
    :param physical_layer: what type is the physical layer
    :type physical_layer: value from the
        :class:`~cyberdem.enumerations.PhysicalLayerType` enumeration, optional
    :param data_link_protocol: data link protocol
    :type data_link_protocol: value from the
        :class:`~cyberdem.enumerations.DataLinkProtocolType` enumeration,
        optional
    :param bandwidth: Max data transfer rate of the link in bps
    :type bandwidth: integer, optional
    :param latency: network link latency in milliseconds
    :type latency: integer, optional
    :param jitter: variability in the latency, measured in milliseconds
    :type jitter: integer, optional
    :param network_interfaces: mapping of interface names to addresses
    :type network_interfaces: list of lists, optional
    :param kwargs: Arguments to pass to the :class:`_CyberObject` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import NetworkLink
        >>> kwargs = {
        ...    'is_logical': False,
        ...    'physical_layer': 'Wired',
        ...    'data_link_protocol': 'Ethernet',
        ...    'bandwidth': 5,
        ...    'name': 'Link 10',
        ...    'description': 'User network link'
        ... }
        >>> net_ints = [['eth1','192.168.10.100'], ['eth0','192.168.10.101']]
        >>> my_link = NetworkLink(network_interfaces=net_ints, **kwargs)
    """

    _type = "NetworkLink"

    def __init__(
        self,
        is_logical=None,
        physical_layer=None,
        data_link_protocol=None,
        bandwidth=None,
        latency=None,
        jitter=None,
        network_interfaces=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if is_logical:
            self.is_logical = is_logical
        if physical_layer:
            self.physical_layer = physical_layer
        if data_link_protocol:
            self.data_link_protocol = data_link_protocol
        if bandwidth:
            self.bandwidth = bandwidth
        if latency:
            self.latency = latency
        if jitter:
            self.jitter = jitter
        if network_interfaces:
            self.network_interfaces = network_interfaces

    @property
    def is_logical(self):
        return self._is_logical

    @is_logical.setter
    def is_logical(self, value):
        if not isinstance(value, bool):
            raise TypeError(f'{type(value)} is not a valid type for is_logical. Must be boolean.')
        self._is_logical = value

    @is_logical.deleter
    def is_logical(self):
        del self._is_logical

    @property
    def physical_layer(self):
        return self._physical_layer

    @physical_layer.setter
    def physical_layer(self, value):
        PhysicalLayerType()._check_prop(value)
        self._physical_layer = value

    @physical_layer.deleter
    def physical_layer(self):
        del self._physical_layer

    @property
    def data_link_protocol(self):
        return self._data_link_protocol

    @data_link_protocol.setter
    def data_link_protocol(self, value):
        DataLinkProtocolType()._check_prop(value)
        self._data_link_protocol = value

    @data_link_protocol.deleter
    def data_link_protocol(self):
        del self._data_link_protocol

    @property
    def bandwidth(self):
        return self._bandwidth

    @bandwidth.setter
    def bandwidth(self, value):
        if not isinstance(value, int):
            raise TypeError(f'{type(value)} is not a valid type for bandwidth. Must be int.')
        self._bandwidth = value

    @bandwidth.deleter
    def bandwidth(self):
        del self._bandwidth

    @property
    def latency(self):
        return self._latency

    @latency.setter
    def latency(self, value):
        if not isinstance(value, int):
            raise TypeError(f'{type(value)} is not a valid type for latency. Must be int.')
        self._latency = value

    @latency.deleter
    def latency(self):
        del self._latency

    @property
    def jitter(self):
        return self._jitter

    @jitter.setter
    def jitter(self, value):
        if not isinstance(value, int):
            raise TypeError(f'{type(value)} is not a valid type for jitter. Must be int.')
        self._jitter = value

    @jitter.deleter
    def jitter(self):
        del self._jitter

    @property
    def network_interfaces(self):
        return self._network_interfaces

    @network_interfaces.setter
    def network_interfaces(self, value):
        if not isinstance(value, list):
            raise TypeError(
                f'{type(value)} is not a valid type for network_interface.'
                f'Must be a list of lists. Ex. "[[\'eth0\', \'1.2.3.4\'], '
                f'[...]]"'
            )
        for net_int in value:
            if not isinstance(net_int, list):
                raise TypeError(f'{type(net_int)} for {net_int} must be a list. Ex. "[\'eth0\', \'1.2.3.4\']"')
        self._network_interfaces = value

    @network_interfaces.deleter
    def network_interfaces(self):
        del self._network_interfaces


class Persona(_CyberObject):
    """Representation of a Persona object.

    Inherits :class:`_CyberObject`. No additional attributes.

    :Example:
        >>> from cyberdem.base import Persona
        >>> kwargs = {
        ...    'name': 'Attacker 1',
        ...    'description': 'nation-state actor'
        ... }
        >>> attacker_1 = Persona(**kwargs)
    """

    _type = "Persona"


class System(_CyberObject):
    """Representation of a System object.

    Inherits :class:`_CyberObject`.

    :param system_type: Type of system
    :type system_type: value from the
        :class:`~cyberdem.enumerations.SystemType` enumeration, optional
    :param kwargs: Arguments to pass to the :class:`_CyberObject` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import System
        >>> kwargs = {
        ...    'system_type': 'SCADA',
        ...    'name': 'MTU',
        ...    'description': 'Network 1 MTU'
        ... }
        >>> my_system = System(**kwargs)
    """

    _type = "System"

    def __init__(self, system_type=None, **kwargs):
        super().__init__(**kwargs)
        if system_type:
            self.system_type = system_type

    @property
    def system_type(self):
        return self._system_type

    @system_type.setter
    def system_type(self, value):
        SystemType()._check_prop(value)
        self._system_type = value

    @system_type.deleter
    def system_type(self):
        del self._system_type


# Fourth level Cyber DEM CyberObjects
class OperatingSystem(Application):
    """Representation of a OperatingSystem object.

    Inherits :class:`Application`.

    :param os_type: Type of software supporting a computer's basic functions
    :type os_type: value from the
        :class:`~cyberdem.enumerations.OperatingSystemType` enumeration,
        optional
    :param kwargs: Arguments to pass to the :class:`Application` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import OperatingSystem
        >>> kwargs = {
        ...    'os_type': 'MicrosoftWindows',
        ...    'name': 'User machine',
        ...    'description': 'For employees in foo department',
        ...    'version': '10'
        ... }
        >>> my_os = OperatingSystem(**kwargs)
    """

    _type = "OperatingSystem"

    def __init__(self, os_type=None, **kwargs):
        super().__init__(**kwargs)
        if os_type:
            self.os_type = os_type

    @property
    def os_type(self):
        return self._os_type

    @os_type.setter
    def os_type(self, value):
        OperatingSystemType()._check_prop(value)
        self._os_type = value

    @os_type.deleter
    def os_type(self):
        del self._os_type


class Service(Application):
    """Representation of a Service object.

    Inherits :class:`Application`.

    :param service_type: value from the
        :class:`~cyberdem.enumerations.ServiceType` enumeration, optional
    :type service_type: value from the
        :class:`~cyberdem.enumerations.OperatingSystemType` enumeration, optional
    :param address:
    :type address: string, optional
    :param kwargs: Arguments to pass to the :class:`Application` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Service
        >>> kwargs = {
        ...    'service_type': 'EmailServer',
        ...    'version': '15.2.595.4',
        ...    'name': 'Mail Server 1',
        ...    'description': 'external exchange server'
        ... }
        >>> my_service = Service(**kwargs)
    """

    _type = "Service"

    def __init__(self, service_type=None, address=None, **kwargs):
        super().__init__(**kwargs)
        if service_type:
            self.service_type = service_type
        if address:
            self.address = address

    @property
    def service_type(self):
        return self._service_type

    @service_type.setter
    def service_type(self, value):
        ServiceType()._check_prop(value)
        self._service_type = value

    @service_type.deleter
    def service_type(self):
        del self._service_type

    @property
    def address(self):
        return self._address

    @address.setter
    def address(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{type(value)} is not a valid type for address. Must be string.')
        self._address = value

    @address.deleter
    def address(self):
        del self._address


class CommunicationsData(Data):
    """Representation of a CommunicationsData object.

    Inherits :class:`Data`.

    :param packet_size: Average size (in bytes) of individual packets
    :type packet_size: integer, optional
    :param packet_size_standard_deviation: Variability of packet sizes (0.0 for fixed sized packets)
    :type packet_size_standard_deviation: float, optional
    :param frequency: Packets per second
    :type frequency: float, optional
    :param duplex: True if the communications bidirectional
    :type duplex: boolean, optional
    :param kwargs: Arguments to pass to the :class:`Data` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import CommunicationsData
        >>> kwargs = {
        ...    'name': 'Data Stream',
        ...    'packet_size': 256,
        ...    'frequency': 3.8,
        ...    'duplex': False
        ... }
        >>> my_comm_data = CommunicationsData(**kwargs)
    """

    _type = "CommunicationsData"

    def __init__(self, packet_size=None, packet_size_standard_deviation=None, frequency=None, duplex=None, **kwargs):
        super().__init__(**kwargs)
        if packet_size:
            self.packet_size = packet_size
        if packet_size_standard_deviation:
            self.packet_size_standard_deviation = packet_size_standard_deviation
        if frequency:
            self.frequency = frequency
        if duplex:
            self.duplex = duplex

    @property
    def packet_size(self):
        return self._packet_size

    @packet_size.setter
    def packet_size(self, value):
        if not isinstance(value, int):
            raise TypeError(f'{type(value)} is not a valid type for packet_size. Must be integer.')
        self._packet_size = value

    @packet_size.deleter
    def packet_size(self):
        del self._packet_size

    @property
    def packet_size_standard_deviation(self):
        return self._packet_size_standard_deviation

    @packet_size_standard_deviation.setter
    def packet_size_standard_deviation(self, value):
        if not isinstance(value, float):
            raise TypeError(f'{type(value)} is not a valid type for packet_size_standard_deviation. Must be float.')
        self._packet_size_standard_deviation = value

    @packet_size_standard_deviation.deleter
    def packet_size_standard_deviation(self):
        del self._packet_size_standard_deviation

    @property
    def frequency(self):
        return self._frequency

    @frequency.setter
    def frequency(self, value):
        if not isinstance(value, float):
            raise TypeError(f'{type(value)} is not a valid type for frequency. Must be float.')
        self._frequency = value

    @frequency.deleter
    def frequency(self):
        del self._frequency

    @property
    def duplex(self):
        return self._duplex

    @duplex.setter
    def duplex(self, value):
        if not isinstance(value, bool):
            raise TypeError(f'{type(value)} is not a valid type for duplex. Must be boolean.')
        self._duplex = value

    @duplex.deleter
    def duplex(self):
        del self._duplex


# Fourth level Cyber DEM CyberEvents
class CyberAdmin(_CyberAction):
    """Representation of a CyberAdmin object.

    Inherits :class:`_CyberAction`.

    :param admin_type: Type of cyber action of an administration nature
    :type admin_type: value from the :class:`~cyberdem.enumerations.AdminType`
         enumeration, optional
    :param kwargs: Arguments to pass to the :class:`_CyberAction` class
    :type kwargs: dictionary, optional

    :Example: TODO
    """

    _type = "CyberAdmin"

    def __init__(self, admin_type=None, **kwargs):
        super().__init__(**kwargs)
        if admin_type:
            self.admin_type = admin_type

    @property
    def admin_type(self):
        return self._admin_type

    @admin_type.setter
    def admin_type(self, value):
        AdminType._check_prop(value)
        self._admin_type = value

    @admin_type.deleter
    def admin_type(self):
        del self._admin_type


class CyberAttack(_CyberAction):
    """Representation of a CyberAttack object.

    Inherits :class:`_CyberAction`. No additional attributes.

    :param mitre_attack_subtechnique_ids: References to MITRE's ATT&CK Sub-techniques
    :type mitre_attack_subtechnique_ids: list of strings, optional
    :param kwargs: Arguments to pass to the :class:`_CyberAction` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import CyberAttack
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'target_modifiers': {"characteristic":"value"},
        ...    'phase': 'Continue',
        ...    'duration': timedelta(seconds=10),
        ...    'actor_ids': [attacker_1.id]
        ... }
        >>> generic_attack = CyberAttack(**kwargs)
    """

    _type = "CyberAttack"

    def __init__(self, mitre_attack_subtechnique_ids=None, **kwargs):
        super().__init__(**kwargs)
        if mitre_attack_subtechnique_ids:
            self.mitre_attack_subtechnique_ids = mitre_attack_subtechnique_ids

    @property
    def mitre_attack_subtechnique_ids(self):
        return self._mitre_attack_subtechnique_ids

    @mitre_attack_subtechnique_ids.setter
    def mitre_attack_subtechnique_ids(self, value):
        if not isinstance(value, list):
            raise TypeError(
                f'{type(value)} is not a valid type for mitre_attack_subtechnique_ids. Must be list of strings.'
            )
        for v in value:
            if not isinstance(v, str):
                raise TypeError(f'CyberAttack mitre_attack_subtechnique_ids list takes only string types.')
        self._mitre_attack_subtechnique_ids = value

    @mitre_attack_subtechnique_ids.deleter
    def mitre_attack_subtechnique_ids(self):
        del self._mitre_attack_subtechnique_ids


class CyberDefend(_CyberAction):
    """Representation of a CyberDefend object.

    Inherits :class:`_CyberAction`.

    :param mitre_attack_mitigation_ids: References to MITRE's ATT&CK Mitigations
    :type mitre_attack_mitigation_ids: list of strings, optional
    :param kwargs: Arguments to pass to the :class:`_CyberAction` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import CyberDefend
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'target_modifiers': {"characteristic":"value"},
        ...    'phase': 'Start',
        ...    'source_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> generic_defend = CyberDefend(**kwargs)
    """

    _type = "CyberDefend"

    def __init__(self, mitre_attack_mitigation_ids=None, **kwargs):
        super().__init__(**kwargs)
        if mitre_attack_mitigation_ids:
            self.mitre_attack_mitigation_ids = mitre_attack_mitigation_ids

    @property
    def mitre_attack_mitigation_ids(self):
        return self._mitre_attack_mitigation_ids

    @mitre_attack_mitigation_ids.setter
    def mitre_attack_mitigation_ids(self, value):
        if not isinstance(value, list):
            raise TypeError(
                f'{type(value)} is not a valid type for mitre_attack_mitigation_ids. Must be list of strings.'
            )
        for v in value:
            if not isinstance(v, str):
                raise TypeError(f'CyberAttack mitre_attack_mitigation_ids list takes only string types.')
        self._mitre_attack_mitigation_ids = value

    @mitre_attack_mitigation_ids.deleter
    def mitre_attack_mitigation_ids(self):
        del self._mitre_attack_mitigation_ids


class CyberRecon(_CyberAction):
    """Representation of a CyberRecon object.

    Inherits :class:`_CyberAction`.

    :param recon_type: Type of reconnaissance
    :type recon_type: value from the :class:`~cyberdem.enumerations.ReconType`
         enumeration, optional
    :param mitre_attack_detection_ids: References to MITRE's ATT&CK Detections
    :type mitre_attack_detection_ids: list of strings, optional
    :param kwargs: Arguments to pass to the :class:`_CyberAction` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import CyberDefend
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'recon_type': 'NetworkMap',
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'source_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> recon_event = CyberRecon(**kwargs)
    """

    _type = "CyberRecon"

    def __init__(self, recon_type=None, mitre_attack_detection_ids=None, **kwargs):
        super().__init__(**kwargs)
        if recon_type:
            self.recon_type = recon_type
        if mitre_attack_detection_ids:
            self.mitre_attack_detection_ids = mitre_attack_detection_ids

    @property
    def recon_type(self):
        return self._recon_type

    @recon_type.setter
    def recon_type(self, value):
        ReconType()._check_prop(value)
        self._recon_type = value

    @recon_type.deleter
    def recon_type(self):
        del self._recon_type

    @property
    def mitre_attack_detection_ids(self):
        return self._mitre_attack_detection_ids

    @mitre_attack_detection_ids.setter
    def mitre_attack_detection_ids(self, value):
        if not isinstance(value, list):
            raise TypeError(
                f'{type(value)} is not a valid type for mitre_attack_detection_ids. Must be list of strings.'
            )
        for v in value:
            if not isinstance(v, str):
                raise TypeError(f'CyberAttack mitre_attack_detection_ids list takes only string types.')
        self._mitre_attack_detection_ids = value

    @mitre_attack_detection_ids.deleter
    def mitre_attack_detection_ids(self):
        del self._mitre_attack_detection_ids


class Deny(_CyberEffect):
    """
    To prevent access to, operation of, or availability of a target function by
    a specified level for a specified time, by degrade, disrupt, or destroy
    (JP3-12)

    Inherits :class:`_CyberEffect`. No additional attributes.

    :param kwargs: Arguments to pass to the :class:`_CyberEffect` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Deny
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> deny_effect = Deny(**kwargs)
    """

    _type = "Deny"


class Detect(_CyberEffect):
    """
    To discover or discern the existence, presence, or fact of an intrusion
    into information systems.

    Inherits :class:`_CyberEffect`.

    :param acquired_information: Key-value pairs describing information
        acquired as a result of a Detect Cyber Effect
    :type acquired_information: dictionary, optional
    :param kwargs: Arguments to pass to the :class:`_CyberEffect` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Detect
        >>> from datetime import datetime, timedelta
        >>> info = {'siem log': 'file permission change on user-ws-2'}
        >>> kwargs = {
        ...    'acquired_information': info,
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> detect_effect = Detect(**kwargs)
    """

    _type = "Detect"

    def __init__(self, acquired_information=None, **kwargs):
        super().__init__(**kwargs)
        if acquired_information:
            self.acquired_information = acquired_information

    @property
    def acquired_information(self):
        return self._acquired_information

    @acquired_information.setter
    def acquired_information(self, value):
        if not isinstance(value, dict):
            raise TypeError(f'{type(value)} is not a valid type for acquired_information. Must be dict.')
        self._acquired_information = value

    @acquired_information.deleter
    def acquired_information(self):
        del self._acquired_information


class Manipulate(_CyberEffect):
    """
    The effect of controlling or changing information, information systems,
    and/or networks to create physical denial effects, using deception,
    decoying, conditioning, spoofing, falsification, and other similar
    techniques.

    Inherits :class:`_CyberEffect`.

    :param kwargs: Arguments to pass to the :class:`_CyberEffect` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Manipulate
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'description': "ransomware encrypted drives",
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'duration': timedelta(hours=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> manipulate_effect = Manipulate(**kwargs)
    """

    _type = "Manipulate"


# Fifth level Cyber DEM CyberEvents
class DataExfiltration(CyberAttack):
    """
    Data exfiltration is the unauthorized copying, transfer or retrieval of
    data from a computer or server. Data exfiltration is a malicious activity
    performed through various different techniques, typically by cybercriminals
    over the Internet or other network.

    Inherits :class:`CyberAttack`. No additional attributes.

    :param kwargs: Arguments to pass to the :class:`CyberAttack` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import DataExfiltration
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'event_time': datetime.today(),
        ...    'phase': 'End',
        ...    'target_ids': [the_target.id],
        ...    'duration': timedelta(hours=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> exfil = DataExfiltration(**kwargs)
    """

    _type = "DataExfiltration"


class Destroy(Deny):
    """
    To completely and irreparably deny access to, or operation of, a target.

    Inherits :class:`Deny`. No additional attributes.

    :param kwargs: Arguments to pass to the :class:`Deny` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Destroy
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> destroy_effect = Destroy(**kwargs)
    """

    _type = "Destroy"


class Degrade(Deny):
    """
    To deny access to, or operation of, a target to a level represented as a
    percentage of capacity

    Inherits :class:`Deny`.

    :param is_random: whether or not the disruption is uniform or random
    :type is_random: boolean, optional
    :param percentage: Percentage of degradation (where 100.0 is equivalent to disrupt)
    :type percentage: float, optional
    :param kwargs: Arguments to pass to the :class:`Deny` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Degrade
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'is_random': False,
        ...    'percentage': .7,
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> degrade_effect = Degrade(**kwargs)
    """

    _type = "Degrade"

    def __init__(self, is_random=None, percentage=None, **kwargs):
        super().__init__(**kwargs)
        if is_random:
            self.is_random = is_random
        if percentage:
            self.percentage = percentage

    @property
    def is_random(self):
        return self._is_random

    @is_random.setter
    def is_random(self, value):
        if not isinstance(value, bool):
            raise TypeError(f'{type(value)} is not a valid type for percentage. Must be boolean.')
        self._is_random = value

    @is_random.deleter
    def is_random(self):
        del self._is_random

    @property
    def percentage(self):
        return self._percentage

    @percentage.setter
    def percentage(self, value):
        if not isinstance(value, float):
            raise TypeError(f'{type(value)} is not a valid type for percentage. Must be float.')
        self._percentage = value

    @percentage.deleter
    def percentage(self):
        del self._percentage


class Disrupt(Deny):
    """
    To completely but temporarily deny access to, or operation of, a target for
    a period of time.

    Inherits :class:`Deny`.

    :param kwargs: Arguments to pass to the :class:`Deny` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import Disrupt
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> disrupt_effect = Disrupt(**kwargs)
    """

    _type = "Disrupt"


class ManipulationEffect(Manipulate):
    """
    A Manipulation Effect describes the type, effected information/system/network,
    and/or extent (as a percentage) of the manipulation attack.

    Inherits :class:`Manipulate`.

    :param manipulation_type: type of manipulation
    :type manipulation_type: value from
        :class:`~cyberdem.enumerations.ManipulationType` enumeration,
        optional
    :param packet_manipulation_type: type of packet manipulation
    :type packet_manipulation_type: value from
        :class:`~cyberdem.enumerations.PacketManipulationType` enumeration,
        optional
    :param percentage: Percentage of packets to affect between 0.0 and 100.0
    :type percentage: float, optional
    :param kwargs: Arguments to pass to the :class:`Manipulate` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import ManipulationEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'manipulation_type': 'Dropped',
        ...    'percentage': 1,
        ...    'description': "dropping packets",
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'duration': timedelta(hours=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> manipulation_effect = ManipulationEffect(**kwargs)

    """

    _type = "ManipulationEffect"

    def __init__(self, manipulation_type=None, packet_manipulation_type=None, percentage=None, **kwargs):
        super().__init__(**kwargs)
        if manipulation_type:
            self.manipulation_type = manipulation_type
        if packet_manipulation_type:
            self.packet_manipulation_type = packet_manipulation_type
        if percentage:
            self.percentage = percentage

    @property
    def manipulation_type(self):
        return self._manipulation_type

    @manipulation_type.setter
    def manipulation_type(self, value):
        ManipulationType()._check_prop(value)
        self._manipulation_type = value

    @manipulation_type.deleter
    def manipulation_type(self):
        del self._manipulation_type

    @property
    def packet_manipulation_type(self):
        return self._packet_manipulation_type

    @packet_manipulation_type.setter
    def packet_manipulation_type(self, value):
        PacketManipulationType()._check_prop(value)
        self._packet_manipulation_type = value

    @packet_manipulation_type.deleter
    def packet_manipulation_type(self):
        del self._packet_manipulation_type

    @property
    def percentage(self):
        return self._percentage

    @percentage.setter
    def percentage(self, value):
        if not isinstance(value, float):
            raise TypeError(f'{type(value)} is not a valid type for percentage. Must be float.')
        self._percentage = value

    @percentage.deleter
    def percentage(self):
        del self._percentage


class ManipulationAttack(CyberAttack):
    """
    Controls or changes information, information systems, and/or networks to
    create physical denial effects, using deception, decoying, conditioning,
    spoofing, falsification, and other similar techniques.

    Inherits :class:`CyberAttack`.

    :param description: Describes the "what and how" of the manipulation attack
    :type description: string, optional
    :param attack_content: could contain the details of the manipulation attack
        itself OR the manipulated message after the attack
    :type attack_content: string, optional
    :param kwargs: Arguments to pass to the :class:`CyberAttack` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import DataExfiltration
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'event_time': datetime.today(),
        ...    'phase': 'End',
        ...    'target_ids': [the_target.id],
        ...    'duration': timedelta(hours=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> exfil = DataExfiltration(**kwargs)
    """

    _type = "ManipulationAttack"


class PhishingAttack(CyberAttack):
    """
    The fraudulent practice of sending messages purporting to be from reputable
    sources in order to induce individuals to reveal sensitive information or
    unknowingly initiate another attack.

    Inherits :class:`CyberAttack`.

    :param message_type: Type of the message used in the attack
    :type message_type: value from the
        :class:`~cyberdem.enumerations.MessageType` enumeration, optional
    :param header: Originator, From, To, Subject, Reply To
    :type header: string, optional
    :param body: The body/content of the email/message
    :type body: string, optional
    :param kwargs: Arguments to pass to the :class:`CyberAttack` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import PhishingAttack
        >>> from datetime import datetime
        >>> kwargs = {
        ...    'message_type': 'Email',
        ...    'header': 'From: Your Name <yourname@foo.bar>, To: My Name \
            <myname@bar.foo>, Subject: foo the bar',
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> phish = PhishingAttack(**kwargs)
    """

    _type = "PhishingAttack"

    def __init__(self, message_type=None, header=None, body=None, **kwargs):
        super().__init__(**kwargs)
        if message_type:
            self.message_type = message_type
        if header:
            self.header = header
        if body:
            self.body = body

    @property
    def message_type(self):
        return self._message_type

    @message_type.setter
    def message_type(self, value):
        MessageType()._check_prop(value)
        self._message_type = value

    @message_type.deleter
    def message_type(self):
        del self._message_type

    @property
    def header(self):
        return self._header

    @header.setter
    def header(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{type(value)} is not a valid type for header. Must be string.')
        self._header = value

    @header.deleter
    def header(self):
        del self._header

    @property
    def body(self):
        return self._body

    @body.setter
    def body(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{type(value)} is not a valid type for body. Must be string.')
        self._body = value

    @body.deleter
    def body(self):
        del self._body


# Sixth level Cyber DEM CyberEvents --> CyberEffects
class BlockTrafficEffect(Disrupt):
    """
    Completely block all traffic over a communication channel.

    Inherits :class:`Disrupt`. No additional attributes.

    :param kwargs: Arguments to pass to the :class:`Disrupt` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import BlockTrafficEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'is_random': False,
        ...    'percentage': .7,
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Continue',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> blocktraffic_effect = BlockTrafficEffect(**kwargs)
    """

    _type = "BlockTrafficEffect"


class HardwareDamageEffect(Destroy):
    """
    Physical damage to a device.

    Inherits :class:`Destroy`.

    :param damage_type: type of damage
    :type damage_type: value from the
        :class:`~cyberdem.enumerations.HardwareDamageType` enumeration,
        optional
    :param kwargs: Arguments to pass to the :class:`Destroy` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import HardwareDamageEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'damage_type': 'PhysicalDestruction',
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(days=5)
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> hwdamage_effect = HardwareDamageEffect(**kwargs)
    """

    _type = "HardwareDamageEffect"

    def __init__(self, damage_type=None, **kwargs):
        super().__init__(**kwargs)
        if damage_type:
            self.damage_type = damage_type

    @property
    def damage_type(self):
        return self._damage_type

    @damage_type.setter
    def damage_type(self, value):
        HardwareDamageType()._check_prop(value)
        self._damage_type = value

    @damage_type.deleter
    def damage_type(self):
        del self._damage_type


class CPULoadEffect(Degrade):
    """
    Artificial increase in CPU load.

    Inherits :class:`Degrade`.

    :param percentage: Percentage of CPU usage between 0.0 and 100.0
    :type percentage: float, optional
    :param kwargs: Arguments to pass to the :class:`Degrade` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import CPULoadEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'percentage': 70,
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> cpuload_effect = CPULoadEffect(**kwargs)
    """

    _type = "CPULoadEffect"


class DelayEffect(Degrade):
    """
    Increased time for data to travel between two points

    Inherits :class:`Degrade`.

    :param seconds: Number of seconds to delay delivery of data
    :type seconds: float, optional
    :param kwargs: Arguments to pass to the :class:`Degrade` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import DelayEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'seconds': 22.5,
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'duration': timedelta(minutes=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> delay_effect = DelayEffect(**kwargs)
    """

    _type = "DelayEffect"

    def __init__(self, seconds=None, **kwargs):
        super().__init__(**kwargs)
        if seconds:
            self.seconds = seconds

    @property
    def seconds(self):
        return self._seconds

    @seconds.setter
    def seconds(self, value):
        if not isinstance(value, float):
            raise TypeError(f'{type(value)} is not a valid type for seconds. Must be float.')
        self._seconds = value

    @seconds.deleter
    def seconds(self):
        del self._seconds


class DropEffect(Degrade):
    """
    Packet dropping.

    Inherits :class:`Degrade`.

    :param kwargs: Arguments to pass to the :class:`Degrade` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import DropEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'percentage': 99.5,
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> pdrop_effect = DropEffect(**kwargs)
    """

    _type = "DropEffect"


class HardwareDegradeEffect(Degrade):
    """
    Degradation, but not destruction of, hardware.

    Inherits :class:`Degrade`.

    :param degrade_type: value from the
        :class:`~cyberdem.enumerations.HardwareDegradeType` enumeration
    :type degrade_type: string, optional
    :param kwargs: Arguments to pass to the :class:`Degrade` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import HardwareDegradeEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'degrade_type': 'BlueScreen',
        ...    'percentage': 90,
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> hw_effect = HardwareDegradeEffect(**kwargs)
    """

    _type = "HardwareDegradeEffect"

    def __init__(self, degrade_type=None, **kwargs):
        super().__init__(**kwargs)
        if degrade_type:
            self.degrade_type = degrade_type

    @property
    def degrade_type(self):
        return self._degrade_type

    @degrade_type.setter
    def degrade_type(self, value):
        HardwareDegradeType()._check_prop(value)
        self._degrade_type = value

    @degrade_type.deleter
    def degrade_type(self):
        del self._degrade_type


class JitterEffect(Degrade):
    """
    Class for JitterEffect object.

    Inherits :class:`Degrade`.

    :param milliseconds: Time delay variance
    :type milliseconds: integer, optional
    :param kwargs: Arguments to pass to the :class:`Degrade` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import JitterEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'milliseconds': 22.5,
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'duration': timedelta(minutes=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> jitter_effect = JitterEffect(**kwargs)
    """

    _type = "JitterEffect"

    def __init__(self, milliseconds=None, **kwargs):
        super().__init__(**kwargs)
        if milliseconds:
            self.milliseconds = milliseconds

    @property
    def milliseconds(self):
        return self._milliseconds

    @milliseconds.setter
    def milliseconds(self, value):
        if not isinstance(value, int):
            raise TypeError(f'{type(value)} is not a valid type for milliseconds. Must be integer.')
        self._milliseconds = value

    @milliseconds.deleter
    def milliseconds(self):
        del self._milliseconds


class LoadRateEffect(Degrade):
    """
    Impact on data upload or download rate.

    Inherits :class:`Degrade`.

    :param rate_type: Type (direction) of load that is effected
    :type rate_type: value from the
        :class:`~cyberdem.enumerations.LoadRateType` enumeration, optional
    :param kwargs: Arguments to pass to the :class:`Degrade` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import LoadRateEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'percentage': 22.5,
        ...    'rate_type': 'Upload',
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> loadrate_effect = LoadRateEffect(**kwargs)
    """

    _type = "LoadRateEffect"

    def __init__(self, rate_type=None, **kwargs):
        super().__init__(**kwargs)
        if rate_type:
            self.rate_type = rate_type

    @property
    def rate_type(self):
        return self._rate_type

    @rate_type.setter
    def rate_type(self, value):
        LoadRateType()._check_prop(value)
        self._rate_type = value

    @rate_type.deleter
    def rate_type(self):
        del self._rate_type


class MemoryUseEffect(Degrade):
    """
    Artificial increase in memory usage.

    Inherits :class:`Degrade`.

    :param percentage: Percentage of memory to use between 0.0 and 100.0
    :type percentage: float, optional
    :param kwargs: Arguments to pass to the :class:`Degrade` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import MemoryUseEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'percentage': 70,
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> memuse_effect = MemoryUseEffect(**kwargs)
    """

    _type = "MemoryUseEffect"


class OtherDegradeEffect(Degrade):
    """
    Generic degradation effect.

    Inherits :class:`Degrade`.

    :param kwargs: Arguments to pass to the :class:`Degrade` class
    :type kwargs: dictionary, optional

    :Example:
        >>> from cyberdem.base import OtherDegradeEffect
        >>> from datetime import datetime, timedelta
        >>> kwargs = {
        ...    'degrade_type': 'BlueScreen',
        ...    'percentage': 90,
        ...    'event_time': datetime.today(),
        ...    'target_ids': [the_target.id],
        ...    'phase': 'Start',
        ...    'duration': timedelta(seconds=5),
        ...    'actor_ids': ["77545b7d-3900-4e34-a26f-eec5eb954d33"]
        ... }
        >>> other_effect = OtherDegradeEffect(**kwargs)
    """

    _type = "OtherDegradeEffect"


class Relationship:
    """Represents a relationship between two CyberObjects.

    Given two CyberObjects A and B, where A administers B, the
    ``related_object_1`` would be the id of A and ``related_object_2`` would be
    the ID of B, preserving the ordering of "A administers B".

    :param related_object_1: ID of a CyberObject
    :type related_object_1: UUIDv4 string, required
    :param related_object_2: ID of a CyberObject
    :type related_object_2: UUIDv4 string, required
    :param relationship_type: value from
        :class:`~cyberdem.enumerations.RelationshipType`
    :type relationship_type: string, optional
    :param id: unique ID (UUIDv4)
    :type id: string, optional
    :param privileges: List of privileges the object with respect to the related object
    :type privileges: list of strings, optional

    :Example:
        >>> # Where my_application is installed on my_device
        >>> from cyberdem.base import Application, Device, Relationship
        >>> my_application = Application()
        >>> my_device = Device()
        >>> my_rel = Relationship(
        ...    my_device.id, my_application.id,
        ...    relationship_type='ResidesOn', privileges=['priv1', 'priv2'])
    """

    _type = "Relationship"

    def __init__(self, related_object_1, related_object_2, relationship_type=None, id=None, privileges=None):
        if id is None:
            id = str(uuid.uuid4())
        self.id = id
        self.related_object_1 = related_object_1
        self.related_object_2 = related_object_2
        if relationship_type:
            self.relationship_type = relationship_type
        if privileges:
            self.privileges = privileges

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        try:
            uuid.UUID(value)
        except ValueError:
            raise ValueError(f'"{value}" is not a valid value for id. Must be a UUIDv4.')
        self._id = value

    @property
    def related_object_1(self):
        return self._related_object_1

    @related_object_1.setter
    def related_object_1(self, value):
        try:
            uuid.UUID(value)
        except ValueError:
            raise ValueError(f'"{value}" is not a valid value for related_object_1. Must be a UUIDv4 in string format')
        self._related_object_1 = value

    @property
    def related_object_2(self):
        return self._related_object_2

    @related_object_2.setter
    def related_object_2(self, value):
        try:
            uuid.UUID(value)
        except ValueError:
            raise ValueError(f'"{value}" is not a valid value for related_object_2. Must be a UUIDv4 in string format')
        self._related_object_2 = value

    @property
    def relationship_type(self):
        return self._relationship_type

    @relationship_type.setter
    def relationship_type(self, value):
        RelationshipType()._check_prop(value)
        self._relationship_type = value

    @relationship_type.deleter
    def relationship_type(self):
        del self._relationship_type

    @property
    def privileges(self):
        return self._privileges

    @privileges.setter
    def privileges(self, value):
        if not isinstance(value, list):
            raise TypeError(f'{type(value)} is not a valid type for privileges. Must be list of strings.')
        for v in value:
            if not isinstance(v, str):
                raise TypeError(f'RelatedObject privilege list takes only string types')
        self._privileges = value

    @privileges.deleter
    def privileges(self):
        del self._privileges

    def _serialize(self):
        serialized = {}
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                serialized[key[1:]] = value
            else:
                serialized[key] = value
        serialized['_type'] = self._type
        return serialized
