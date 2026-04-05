package it.csec.xtext.vsdl.Terraform

import java.util.Hashtable
import it.csec.xtext.generator.VsdlConsole
import org.eclipse.xtend.lib.annotations.Accessors
import org.eclipse.core.resources.ResourcesPlugin
import it.csec.xtext.VsdlResources
import java.io.ByteArrayInputStream
import org.eclipse.core.resources.IResource

class Scenario {
	@Accessors
	private var Hashtable<String, Hashtable<Integer,Node>> nodes
	@Accessors
	private var Hashtable<String, Hashtable<Integer,Network>> networks
	@Accessors
	private var VsdlConsole console
	@Accessors
	private var String name	
	@Accessors
	private var int ttu	

	new(String name) {
		nodes = new Hashtable<String, Hashtable<Integer,Node>>()
		networks = new Hashtable<String, Hashtable<Integer,Network>>()
		this.name = name
		console = new VsdlConsole(name + " Terraform Script")
		ttu = 0
	}
	
	def public createResource(String name, int ttuStep, String content) {
		var project = ResourcesPlugin.getWorkspace().getRoot().getProjects().get(0);
		var folder = project.getFolder("src-gen/" + this.name + "_" + ttuStep);
		if (! folder.exists) {
			folder.create(true, true, null)
		}
		
		var file = folder.getFile(name);
		var bis = new ByteArrayInputStream(content.toString.bytes)
		
		if (file.exists) {
			file.delete(true, true, null)
		}
		
		file.create(bis, IResource.NONE, null);	
	}
	
	def public doTerraformProvider() {
		'''
		provider "openstack" {
		    user_name  = "«VsdlResources.OSuser»"
		    tenant_name = "«VsdlResources.OStenant»"
		    password  = "«VsdlResources.OSpassword»"
		    auth_url  = "«VsdlResources.OSurl»"
		}
		'''
	}
	
	def public doTerraformBogusNet() {
		'''
		resource "openstack_networking_network_v2" "bogus" {
		  name = "bogus"
		  admin_state_up = "true"
		}
		
		resource "openstack_networking_subnet_v2" "subnet_bogus" {
		  name = "subnet_bogus"
		  network_id = "${openstack_networking_network_v2.bogus.id}"
		  cidr = "240.0.0.0/16"
		  ip_version = 4
		}
		'''
	}
	
	def public setElementFromValue(String value) {
		if ((value.substring(0,3) != "(((") && (value.substring(value.length - 2) != "))")) {
			throw new Exception("Invalid value format")
		}
		
		var fname = value.substring(3, value.indexOf(" "))
		var ttuStep = value.substring(fname.length + 4, value.indexOf(" ", fname.length + 4))
		var params = value.substring(fname.length + ttuStep.length + 5, 
			value.indexOf(")", fname.length + ttuStep.length + 5)
		)
		var retvalue = value.substring(value.indexOf(")") + 2, value.length - 2)
		
		if (Integer.parseInt(ttuStep) > ttu) {
			ttu = Integer.parseInt(ttuStep)
		}

		if (fname.substring(0, fname.indexOf(".")) == "node") {
			//console.stream.println("NODE: " + fname + "," + ttuStep + "," + params + "," + retvalue)
			if (retvalue.equalsIgnoreCase("false")) {
				retvalue = "0"
			} 

			if (retvalue.equalsIgnoreCase("true")) {
				retvalue = "1"
			} 
						
			NodeValuesFactory(fname.substring(fname.indexOf(".") + 1), Integer.parseInt(ttuStep), Integer.parseInt(retvalue), params.split(" "))					
		} else {
			//console.stream.println("NETWORK: " + fname + "," + ttuStep + "," + params + "," + retvalue)
			if (retvalue.equalsIgnoreCase("false")) {
				retvalue = "0"
			} 

			if (retvalue.equalsIgnoreCase("true")) {
				retvalue = "1"
			} 

			NetworkValuesFactory(fname.substring(fname.indexOf(".") + 1), Integer.parseInt(ttuStep), Long.parseUnsignedLong(retvalue), params.split(" "))			
		}		 
	}
	
	def addNode(String name, String scenario, int ttuStep) {
		if (! nodes.containsKey(name)) {
			//console.stream.println("aggiungi nodo " + name)  
			nodes.put(name, new Hashtable<Integer,Node>)
		} 
		
		if (! nodes.get(name).containsKey(ttuStep)) {
			nodes.get(name).put(ttuStep, new Node(name))
			nodes.get(name).get(ttuStep).scenario = scenario
			nodes.get(name).get(ttuStep).ttuStep = ttuStep
		}		
	}

	def addNetwork(String name, String scenario, int ttuStep) {
		if (! networks.containsKey(name)) {
			networks.put(name, new Hashtable<Integer,Network>)
		}
		
		if (! networks.get(name).containsKey(ttuStep)) {
			networks.get(name).put(ttuStep, new Network(name))
			networks.get(name).get(ttuStep).scenario = scenario
			networks.get(name).get(ttuStep).ttuStep = ttuStep
		}				
	}
	
	def NodeValuesFactory(String fname, int ttuStep, int retvalue, String... params) {
		//console.stream.println("NODE: " + fname + "," + ttuStep + "," + params.get(0) + "," + retvalue)

		addNode(params.get(0), name, ttuStep)
	/* 	if (! nodes.get(params.get(0)).containsKey(ttuStep)) {
			nodes.get(params.get(0)).put(ttuStep, new Node(params.get(0)))
			nodes.get(params.get(0)).get(ttuStep).scenario = name
			nodes.get(params.get(0)).get(ttuStep).ttuStep = ttuStep
		} */
		
		switch (fname) {
			case "vcpu": {
				nodes.get(params.get(0)).get(ttuStep).flavor.vcpu = retvalue
			}
			
			case "disk": {
				nodes.get(params.get(0)).get(ttuStep).flavor.disk = retvalue				
			}
			
			case "ram": {
				nodes.get(params.get(0)).get(ttuStep).flavor.ram = retvalue					
			}
			case "os": {
				nodes.get(params.get(0)).get(ttuStep).OS = retvalue										
			}
		}  
	}

	def NetworkValuesFactory(String fname, int ttuStep, long retvalue, String... params) {
		//console.stream.println("NETWORK: " + fname + "," + ttuStep + "," + params.get(0) + "," + retvalue)
		addNetwork(params.get(0), name, ttuStep)
		
	 	/* if (fname == "node.address") {
			addNode(params.get(1), name, ttuStep)			
		} */
		
		switch (fname) {
			case "address": {
				networks.get(params.get(0)).get(ttuStep).address = Network.long2ip(retvalue)	
			}
			
			case "netmask": {
				networks.get(params.get(0)).get(ttuStep).netmask = retvalue	as int			
			}
			
			case "node.address": {
				 if (retvalue != 0) {
					if (params.get(0) == params.get(1)) {
						// gateway address
						networks.get(params.get(0)).get(ttuStep).gwaddress = Network.long2ip(retvalue)
					} else {		
						if (nodes.containsKey(params.get(1))) {
							console.stream.println("NETWORK: " + params.get(0) + "," + ttuStep + "," + params.get(1) + "," + retvalue)
							
							nodes.get(params.get(1)).get(ttuStep).interfaces.add(new Interface(params.get(0), 
								Network.long2ip(retvalue)
							))
						} else {
							if (networks.containsKey(params.get(1))) {
								networks.get(params.get(0)).get(ttuStep).router.ports.add(
									new Port(params.get(1), Network.long2ip(retvalue))
								)
								networks.get(params.get(0)).get(ttuStep).router.routes.add(
									new Route(networks.get(params.get(1)).get(ttuStep).name,
										networks.get(params.get(1)).get(ttuStep).address,
										networks.get(params.get(1)).get(ttuStep).netmask, Network.long2ip(retvalue)
									)	
								)
								networks.get(params.get(1)).get(ttuStep).router.interfaces.add(
									new Interface(params.get(0), Network.long2ip(retvalue))
								)								
							} else {
								// oooops ..
							}
						}
					}			
				} 
			}
			
			case "gateway.internet": {
				networks.get(params.get(0)).get(ttuStep).router.internet = (retvalue > 0)
			}
		}
		
	}
}