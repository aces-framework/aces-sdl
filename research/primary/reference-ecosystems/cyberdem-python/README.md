# Cyber Data Exchange Model (Cyber DEM) Python Package

## Overview

Cyber DEM Python provides a Python API for the [Cyber Data Exchange Model](https://www.sisostds.org/StandardsActivities/DevelopmentGroups/CyberDEMPDG.aspx) (Cyber DEM). Cyber DEM Python provides methods to instantiate Cyber DEM objects and events, serialize and deserialize objects and events, and manipulate instantiated objects. It also provides basic searching and file management methods.

## Getting Started

These instructions will help you install a copy of the package on your local machine.

### Install with pip

``` sh
pip3 install cyberdem
```

### Installing from source

1. Download Cyber DEM Python and unzip the download folder
2. From within the top-level cyberdem folder (where [setup.py](setup.py) is located) run

``` sh
pip3 install .
```

3. To test that cyberdem is installed properly run

``` py
$ python3
>>> from cyberdem import base
>>> print(base.System())
System(
    id: 3bb3512e-dc75-4b86-b234-25040a79b9b9
)
```

You may also try running the example.py file downloaded with the zip file in [examples/scripts](examples/scripts).

``` py
$ python3 example.py
Creating new FileSystem path ./test-fs.

QUERY 1
--------
['description', 'id', 'name', 'version', '_type']
('Rapid SCADA software', '0f717dfa-...', 'Rapid SCADA', '5', 'Application')
('PfSense Firewall', '2720359e-...', 'PfSense', '2.4.2', 'Application')
(None, '2f6ac399-...', None, None, 'Application')
(None, 'd36e99ce-...', None, None, 'Application')
('Firefox browser', 'df8478d6-...', 'Firefox', '60', 'Application')
(None, '0eaacdbc-...', None, None, 'Application')
(None, '6265eb88-...', None, None, 'Application')

QUERY 2
--------
['description', 'name']
(None, None)
...
(None, None)
(None, None)
('PfSense Firewall', 'PfSense')
(None, None)
('Firefox browser', 'Firefox')
('Rapid SCADA software', 'Rapid SCADA')
...

QUERY 3: SELECT id FROM Application,OperatingSystem WHERE name='PfSense' OR os_type='LinuxRedHat'
--------
['id']
('19a6f4b3-89ce-4aa5-8a94-a065833a3a53',)
('f177a5e0-f56a-4c11-b655-39e6c0cac873',)

Updating app versions...
Application(
    id: 19a6f4b3-89ce-4aa5-8a94-a065833a3a53
    name: PfSense
    version: 2.5.0
)
OperatingSystem(
    id: f177a5e0-f56a-4c11-b655-39e6c0cac873
    os_type: LinuxRedHat
    version: 8.0
)
```

You will see a folder called "test-fs" in the directory in which you ran the [example.py](example.py) script. This folder has subfolders containing each type of Cyber DEM object/event.

### Documentation

The code documentation can be found as a pdf [here](assets/cyberdempython.pdf).

## License

Copyright 2020 Carnegie Mellon University. See the [LICENSE.md](LICENSE.md) file for details.

## Acknowledgements

- [SISO Cyber DEM Product Development Group](https://www.sisostds.org/StandardsActivities/DevelopmentGroups/CyberDEMPDG.aspx)
