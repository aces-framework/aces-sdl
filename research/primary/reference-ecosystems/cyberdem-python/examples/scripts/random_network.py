'''
CyberDEM Example Script for random network generation

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


# This script provides an example of building a random network given some user
# provided parameters, getting a summary of what was generated using the query
# function, then updating the generated assets

from cyberdem.filesystem import FileSystem
from cyberdem.widgets import generate_network

# Set variables
filesystem_path = './test-cyberdem'
num_devices = 50  # the number of physical devices on the network
num_users = 10  # the number of users on the network
heterogeneity = 2  # amount of variety in the network; scale of 0-5
descrip = "Company "  # object description string

# Set up the FileSystem to hold the CyberDEM objects
fs = FileSystem(filesystem_path)

# Generate an enterprise network (default purpose)  
generate_network(num_devices, num_users, fs, heterogeneity=heterogeneity)

# Get a summary of the devices on the network
query = "SELECT name,description,device_types,id FROM Device"
headers, resp = fs.query(query)
print('\t | '.join(headers))
for line in resp:
    print('\t | '.join([str(l) for l in line]))

# Update the devices with custom descriptions
print("\nUpdating...")
name_type_counter = {}
for obj in resp:
    cd_object = fs.get(obj[3])
    types = [t.lower() for t in obj[2]]
    description = descrip + obj[0].lower()
    cd_object.description = description
    fs.save(cd_object, overwrite=True)

# Rerun the summary query after the changes are made
print()
headers, resp = fs.query(query)
print('\t | '.join(headers))
for line in resp:
    print('\t | '.join([str(l) for l in line]))

print(
    f"\nNetwork generation is complete. Your assets are located in "
    f"{filesystem_path}.")