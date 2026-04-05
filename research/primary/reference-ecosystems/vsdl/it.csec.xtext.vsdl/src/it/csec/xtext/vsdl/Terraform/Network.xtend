package it.csec.xtext.vsdl.Terraform

import org.eclipse.xtend.lib.annotations.Accessors

class Network extends ScenElem {
	@Accessors	
	private var String address
	@Accessors	
	private var int netmask
	@Accessors
	private var String gwaddress
	@Accessors
	private boolean internet
	@Accessors
	private Router router
	
	new(String name) {
		this.name = name
		this.address = ""
		this.gwaddress = ""
		this.netmask = 0
		this.internet = false
		router = new Router("rt_" + name)
		router.interfaces.add(0, new Interface(name, ""))
	}
	
	def static public long2ip(long ip) {
		var o4 = Long.toString(ip.bitwiseAnd(0xff))
		var o3 = Long.toString((ip >> 8).bitwiseAnd(0xff))
		var o2 = Long.toString((ip >> 16).bitwiseAnd(0xff))
		var o1 = Long.toString((ip >> 24).bitwiseAnd(0xff))

		return o1 + "." + o2 + "." + o3 + "." + o4
	}
	
	def toTerraformString() {
	'''
	resource "openstack_networking_network_v2" "«name»" {
	  name = "«name»"
	  admin_state_up = "true"
	}
	
	resource "openstack_networking_subnet_v2" "subnet_«name»" {
	  name = "subnet_«name»"
	  network_id = "${openstack_networking_network_v2.«name».id}"
	  cidr = "«address»/«netmask»"
	  ip_version = 4
	  dns_nameservers = ["8.8.8.8", "8.8.4.4"]
	  # enable_dhcp = "true"
	«IF gwaddress !== ""»
	  gateway_ip = "«gwaddress»"
	«ENDIF»	 
	} 
	'''		
	}
}