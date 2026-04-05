"""
Cyber DEM FileSystem Module

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
and unlimited distribution.  Please see Copyright notice for non-US Government
use and distribution.

DM20-0711
"""


from cyberdem import base
from itertools import combinations
import inspect
import json
import os
import re


class FileSystem():
    """Create a directory structure and file storage and retrieval methods.

    Creates file storage, retrieval, and query methods for storing and
    retrieving CyberObjects, CyberEvents, and Relationships.

    :param path: directory path to store Cyber DEM json files; can be existing
        directory or non-existing
    :type path: string, required

    :Example:
        >>> from cyberdem import filesystem
        >>> fs = filesystem.FileSystem("./test-fs")
        Using existing FileSystem at ./test-fs
        >>> fs.path
        './test-fs'
    """

    # find the types of objects allowed from the base module and map the "type"
    # attribute to the class method
    obj_types = {}
    for name, test_obj in inspect.getmembers(base, inspect.isclass):
        if test_obj.__module__ == 'cyberdem.base':
            if test_obj._type:
                obj_types[test_obj._type] = test_obj

    def __init__(self, path):
        """Creates a directory for storing Cyber DEM objects and Events"""

        if not os.path.isdir(path):
            os.mkdir(path)
        self.path = path
        self._folders = []
        for folder in os.listdir(self.path):
            if os.path.isdir(os.path.join(self.path, folder)):
                self._folders.append(folder)

    def _create_folder(self, folder_name):
        """Creates a sub-folder in the FileSystem path

        :param folder_name: should match one of the Cyber DEM base classes
        :type folder_name: string, required
        """

        # sub-folders should match the public classes in the base module
        if folder_name in self.obj_types:
            os.mkdir(self.path + '/' + folder_name)
            self._folders.append(folder_name)
        else:
            raise Exception(
                f'The folder_name "{folder_name}" does not match '
                f'the base classes for Cyber DEM.')

    def load_flatfile(self, filename):
        """Loads Cyber DEM objects and actions from a flat json file into the 
            FileSystem

        :param filename: the json file load
        :type filename: string, required

        :Example:
            >>> fs = FileSystem('./test-fs')
            >>> fs.load_flatfile('cyberdem_input.json')
        """

        with open(filename, 'r') as j_file:
            data = json.load(j_file)
        j_file.close()

        # Check the data first
        for obj_type in data:
            # Each of the primary keys should be a Cyber DEM base class
            if obj_type not in self.obj_types:
                raise ValueError(
                    f"{obj_type} is not a Cyber DEM object or action")

        for obj_type in data:
            for data_obj in data[obj_type]:
                del data_obj['_type']
                obj = self.obj_types[obj_type](**data_obj)
                self.save(obj)

    def save(self, objects, overwrite=False):
        """Save Cyber DEM objects and events to the FileSystem as json files

        :param objects: Cyber DEM object or event instance (or list of
            instances)
        :type objects: Cyber DEM class instance from :py:mod:`base`, or a list
            of objects
        :param overwrite: allow object with the same ID as one already in the
            FileSystem to overwrite the existing file, defaults to False
        :type overwrite: bool, optional

        :raises Exception: if object is already in FileSystem and overwrite is
            set to False

        :Example:
            >>> from cyberdem.base import Service
            >>> my_service = Service(
                    name='httpd', description='Apache web server',\
                    version='2.4.20', service_type='WebService',\
                    address='192.168.100.40')
            >>> fs.save(my_service)
            >>>
            $ ls ./test-fs/Service
            82ca4ed1-a053-4fc1-b1cc-f4b58b4dbf8c.json
        """

        if not isinstance(objects, list):
            objects = [objects]
        for obj in objects:
            if obj._type not in self._folders:
                self._create_folder(obj._type)

            filepath = os.path.join(self.path, obj._type, obj.id)

            if os.path.isfile(filepath+'.json') and not overwrite:
                raise Exception(
                    f'Object {obj.id} already exists in '
                    f'{self.path}. Add "overwrite=True" to overwrite.')

            serialized = obj._serialize()
            with open(filepath + '.json', 'w') as outfile:
                json.dump(serialized, outfile, indent=4)
            outfile.close()

    def get(self, id, obj_type=None):
        """Get an object by ID

        :param id: UUID of object to retrieve
        :type id: string, required
        :param obj_type: Cyber DEM type of the id. Ex. "Application"
        :type obj_type: string, optional

        :return: instance of the requested object
        :rtype: cyberdem instance

        :Example:
            >>> my_object = fs.get("82ca4ed1-a053-4fc1-b1cc-f4b58b4dbf8c",\
                "Application")
            >>> str(my_object)
            Application(
                id: 82ca4ed1-a053-4fc1-b1cc-f4b58b4dbf8c
            )
        """

        # ensure the obj_type specified is allowed
        if obj_type:
            if obj_type not in self.obj_types:
                raise Exception(
                    f'obj_type "{obj_type}" is not an allowed '
                    f'Cyber DEM base type. must be in {self.obj_types}"')
            filepath = os.path.join(self.path, obj_type)
        else:
            filepath = self.path

        if not isinstance(id, str):
            raise Exception(
                f'id of type "{type(id)}" is not allowed. Must be a string.')

        if obj_type:
            # if the object type was specified the search is quicker
            if os.path.isfile(os.path.join(filepath, id) + '.json'):
                with open(os.path.join(filepath, id) + '.json') as j_file:
                    obj = json.load(j_file)
                j_file.close()
        else:
            # otherwise, you have to search through the whole directory
            for root, _, files in os.walk(filepath):
                if id+'.json' in files:
                    obj_type = os.path.split(root)[1]
                    with open(os.path.join(root, id) + '.json') as j_file:
                        obj = json.load(j_file)
                    j_file.close()
        del obj['_type']
        
        return self.obj_types[obj_type](**obj)

    def query(self, query_string):
        """Search the FileSystem for a specific object or objects

        :param query_string: SQL formatted query string
        :type query_string: string, required

        :return: attribute names (headers), values of matching objects
        :rtype: 2-tuple of lists

        :Example query strings:
            * ``SELECT * FROM *`` (you probably shouldn't do this one...)
            * ``SELECT attr1,attr2 FROM * WHERE attr3=value``
            * ``SELECT id,name,description FROM Device,System WHERE name='my \
                device'``
            * ``SELECT id FROM * WHERE (name='foo' AND description='bar') OR\
                 version<>'foobar'``

        :Example:
            >>> query = "SELECT id FROM * WHERE name='Rapid SCADA'"
            >>> fs.query(query)
            (['id'], [('9293510b-534b-4dd0-b7c5-78d92e279400',)])
            >>> query = "SELECT id,name FROM Application"
            >>> headers,results = fs.query(query)
            >>> headers
            ['id','name']
            >>> results
            [('9293510b-534b-4dd0-b7c5-78d92e279400',),\
            ('46545b7a-1840-4e34-a26f-aef5eb954b25','My application')]
        """

        # split the query string into the key components
        if not query_string.upper().startswith("SELECT "):
            raise Exception(
                f'query_string must start with "SELECT ". {query_string}')
        if " FROM " not in query_string.upper():
            raise Exception(
                f'query_string must contain "FROM" statement. {query_string}')
        q_select = query_string[7:query_string.find(" FROM ")]
        q_from = query_string[query_string.find(" FROM ")+6:]
        if " WHERE " in query_string.upper():
            q_where = query_string[query_string.find(" WHERE ")+7:]
            q_from = q_from[:q_from.find(" WHERE ")]
            q_where = q_where.replace('AND', 'and').replace('OR', 'or')
            q_where = q_where.replace('=', '==').replace('<>', '!=')
            q_where = q_where.replace(';', '')
        else:
            q_where = None

        # find all of the paths to search on (all of the object types)
        paths = []
        if q_from == "*":
            for obj_type in self.obj_types:
                if os.path.isdir(os.path.join(self.path, obj_type)):
                    paths.append(os.path.join(self.path, obj_type))
        else:
            for obj_type in q_from.split(','):
                if obj_type not in self.obj_types:
                    raise Exception(
                        f'obj_type "{obj_type}" is not an allowed '
                        f'Cyber DEM base type. must be in {self.obj_types}"')
                # if objects of that type exist in the filesystem
                if obj_type in os.listdir(self.path):
                    paths.append(os.path.join(self.path, obj_type))

        # if the SELECT is *, find all possible class attributes to include
        if q_select == "*":
            get_attrs = []
            for path in paths:
                type_attrs = [
                    a for a in dir(self.obj_types[os.path.split(path)[1]])
                    if not a.startswith('_') and a not in get_attrs]
                get_attrs.extend(type_attrs)
            get_attrs.append('_type')
        else:
            get_attrs = q_select.split(',')

        # find all of the attribute names in the WHERE clause
        if q_where:
            clauses = re.split('and | or', q_where)
            where_attrs = []
            for c in clauses:
                if '==' in c:
                    operator = '=='
                elif '!=' in c:
                    operator = '!='
                elif '<' in c:
                    operator = '<'
                elif '>' in c:
                    operator = '>'
                elif '<=' in c:
                    operator = '<='
                elif '>=' in c:
                    operator = '>='
                else:
                    raise ValueError(f'Unrecognized operator in "{c}"')
                clause = re.split(operator, c)
                attr = clause[0].strip().lstrip('(')
                where_attrs.append((attr, operator))

        # search each file in each path for the desired attributes
        selected = []
        for path in paths:
            for f in os.listdir(path):
                with open(os.path.join(path, f)) as json_file:
                    obj_dict = json.load(json_file)
                json_file.close()

                # check for filtering criteria
                where_check = q_where
                if q_where is not None:
                    for attr in where_attrs:
                        # change out the attribute name in the WHERE clause
                        #   for their values from the current object
                        try:
                            obj_val = obj_dict[attr[0]]
                            where_check = where_check.replace(
                                ''.join(attr), "'"+obj_val+"'"+attr[1])
                        except KeyError:
                            where_check = where_check.replace(
                                ''.join(attr), "'"+attr[0]+"'"+attr[1])

                    matches = eval(where_check)
                    if not matches:
                        continue

                match = ()
                for attr in get_attrs:
                    try:
                        match += (obj_dict[attr],)
                    except KeyError:
                        match += (None,)
                selected.append(match)

        return get_attrs, selected

    def save_networkgraph_data(self, nodes='Device', links='NetworkLinks', output_path=None):
        # Check inputs
        if nodes not in self.obj_types:
            raise TypeError(f"{nodes} is not a Cyber DEM Object or Action")
        if links not in self.obj_types:
            raise TypeError(f"{links} is not a Cyber DEM Object or Action")
    
        # Get the data and put in a d3.js format
        data = {"nodes": [], "links": []}
        _, resp = self.query('SELECT id FROM ' + nodes)
        for node in resp:
            data_object = self.get(node[0], nodes)
            info = {'id': data_object.id, 'name': data_object.name}
            data['nodes'].append(info)

        _, resp = self.query('SELECT id FROM '+ links)
        link_ids = [i[0] for i in resp]

        _, resp = self.query(
            'SELECT related_object_1,related_object_2 FROM Relationship')
        for link in link_ids:
            related = []
            for rel in resp:
                if rel[0] == link:
                    related.append(rel[1])
                if rel[1] == link:
                    related.append(rel[0])
            comb = combinations(related, 2)
            for c in comb:
                data['links'].append({'source':c[0],'target':c[1]})

        # Save to file    
        if output_path:
            path = output_path
        else:
            path = os.path.join(self.path, 'd3js_data.json')
        with open(path, 'w') as f:
            json.dump(data, f)
        f.close()

    def save_flatfile(self, output_path=None, ignore=[]):
        """Saves objects and actions in the filesystem to one flat json file.

        :param output_path: location and path to save the flat file (ex.
            'results\\cd_output.json')
        :type output_path: string, optional (defaults to filesystem path)
        :param ignore: list of Cyber DEM objects or actions (as strings) not to
            indclude in the file
        :type ignore: list of strings, optional

        :Example:
            >>> fs = FileSystem('./test-fs')
            >>> fs.save_flatfile(ignore=['Application'])
        """

        # Check for bad input
        if not isinstance(ignore, list):
            raise TypeError("\"ignore\" must be a list of Cyber DEM objects")
        for obj_type in ignore:
            if obj_type not in self.obj_types:
                raise ValueError(
                    f"{obj_type} in 'ignore' is not a Cyber DEM object or "
                    f"action")

        # iterate through all folders in the file path and add objects to data
        data = {} 
        for folder in os.listdir(self.path):
            if folder in ignore:
                continue
            data[folder] = []
            for datafile in os.listdir(os.path.join(self.path, folder)):
                with open(os.path.join(self.path, folder, datafile)) as j_file:
                    data_object = json.load(j_file)
                j_file.close()
                data[folder].append(data_object)
        if output_path:
            path = output_path
        else:
            path = os.path.join(self.path, 'cyberdem_data.json')
        with open(path, 'w') as f:
            json.dump(data, f)
        f.close()