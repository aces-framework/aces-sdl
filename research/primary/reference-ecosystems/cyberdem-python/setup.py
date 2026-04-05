import pathlib
from setuptools import setup, find_packages

HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text(encoding="utf8")
LICENSE = (HERE / "LICENSE.md").read_text(encoding="utf8")
long_desc = (
    "Cyber DEM Python provides a Python API for the `Cyber Data Exchange Model <https://www.sisostds.org/StandardsActivities/DevelopmentGroups/CyberDEMPDG.aspx>`_ (CyberDEM). CyberDEM Python provides methods to instantiate CyberDEM objects and events, serialize and deserialize objects and events, and manipulate instantiated objects. It also provides basic searching and file management methods. "
    "Status"
    "------"
    "Cyber DEM Python is based on the Cyber DEM standard that is currently in DRAFT format, and therefore subject to change. For the most up to date version and documentation for CyberDEM Python see the CyberDEM Python GitHub page: `https://github.com/cmu-sei/cyberdem-python <https://github.com/cmu-sei/cyberdem-python>`_."
)

setup(
    name="cyberdem",
    version="0.1.0",
    description="Cyber DEM SISO standard python helper package",
    long_description=long_desc,
    # long_description_content_type="text/markdown",
    author="Carnegie Mellon University",
    url="https://github.com/cmu-sei/cyberdem-python",
    license=LICENSE,
    platforms=['any'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    packages=find_packages(),
)
