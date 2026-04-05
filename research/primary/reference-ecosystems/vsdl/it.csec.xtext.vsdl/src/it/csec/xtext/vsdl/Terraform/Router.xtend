package it.csec.xtext.vsdl.Terraform

import org.eclipse.xtend.lib.annotations.Accessors
import java.util.ArrayList

/*
 per ogni rete creo un router
 
 resource "openstack_networking_router_v2" "router_netX" {
  name = "router_netX"
  // se gateway.internet è true:
  external_gateway = "f67f0d72-0ddf-11e4-9d95-e1f29f417e2f"
  // il valore è "cablato" preso da "neutron net-show FLOATING_IP_POOL", valore id
} 
 
 ci vuole una interfaccia fissa sulla rete (default gw della rete)
 spero questa prenda SEMPRE gateway settato nella rete di default
 resource "openstack_networking_router_interface_v2" "router_interface_1" {
  router_id = "${openstack_networking_router_v2.[questo router].id}"
  subnet_id = "${openstack_networking_subnet_v2.[questa sottorete].id}"
}

 se dichiaro che "node.address" in cui il nodo è una rete (rete collegata ad una rete) ho come parametro l'ip
 dichiaro una porta sulla rete
 
 resource "openstack_networking_port_v2" "port_[questarete]_[nomealtrarete]" {
  name = "port_[questarete]_[nomealtrarete]"
  network_id = "${openstack_networking_network_v2.[questarete].id}"
  admin_state_up = "true"
  fixed_ip {
   subnet_id = "${openstack_networking_network_v2.[questasottorete].id}"
   ip_address = "parametro ip"
  }
   
  interfaccia sul router dell'altra rete
  
  resource "openstack_networking_router_interface_v2" "router_interface_[questarete]" {
  router_id = "${openstack_networking_router_v2.router_[altrarete].id}"
  subnet_id = "${openstack_networking_subnet_v2.subnet_[questarete].id}"
  port_id = "${port_[questarete]_[nomealtrarete]}"
}
  
  una route [altrarete] -> "parametro ip" sul router dell'altra rete
  resource "openstack_networking_router_route_v2" "router_route_altrarete_questarete" {
  depends_on = ["openstack_networking_router_interface_v2."]
  router_id = "${openstack_networking_router_v2.router_1.id}"
  destination_cidr = "10.0.1.0/24"
  next_hop = "192.168.199.254"
} 
  
} 

 */
 
class Router {	
	@Accessors
	private String name
	@Accessors
	private boolean internet
	@Accessors
	private var ArrayList<Interface> interfaces
	@Accessors
	private var ArrayList<Route> routes	
	@Accessors
	private var ArrayList<Port> ports	
	
	new(String name) {
		this.name = name
		interfaces = new ArrayList<Interface>
		routes = new ArrayList<Route>
		ports = new ArrayList<Port>
		internet = false
	}
	
	/*
	 */
	// TODO: retrieve automatically external gateway ID
	def toTerraformString() {
		'''
		resource "openstack_networking_router_v2" "router_«name»" {
			name = "router_«name»"
		«IF internet»
			external_gateway = "e041461b-0fba-4153-b186-3f5e9e140b3d"
		«ENDIF» 
		}
				
		«IF interfaces !== null»
		
		resource "openstack_networking_router_interface_v2" "router_«name»_interface_«interfaces.get(0).networkid»" {
		  router_id = "${openstack_networking_router_v2.router_«name».id}"
		  subnet_id = "${openstack_networking_subnet_v2.subnet_«interfaces.get(0).networkid».id}"
		}
		
		«FOR n : interfaces»
		«IF n.networkid != interfaces.get(0).networkid»
		resource "openstack_networking_router_interface_v2" "router_«name»_interface_«n.networkid»" {
		  router_id = "${openstack_networking_router_v2.router_«name».id}"
		  # subnet_id = "${openstack_networking_subnet_v2.subnet_«n.networkid».id}"
		  port_id = "${openstack_networking_port_v2.port_«interfaces.get(0).networkid».id}"
		}		
		«ENDIF»
		«ENDFOR»
		«ENDIF»
		
		«IF ports !== null»
		«FOR p : ports»
		resource "openstack_networking_port_v2" "port_«p.networkid»" {
		  name = "port_«p.networkid»"
		  network_id = "${openstack_networking_network_v2.«interfaces.get(0).networkid».id}"
		  admin_state_up = "true"
		  fixed_ip {
		  	subnet_id = "${openstack_networking_subnet_v2.subnet_«interfaces.get(0).networkid».id}"
		  	ip_address = "«p.address»"
		  }
		}
		«ENDFOR»
		«ENDIF»
		
		«IF routes !== null»		  
		«FOR r : routes»
		resource "openstack_networking_router_route_v2" "router_route_«r.name»" {
			# depends_on = interfaccia? 
			depends_on = ["openstack_networking_port_v2.port_«r.name»"]
			router_id = "${openstack_networking_router_v2.router_«name».id}"
			destination_cidr = "«r.address»/«r.netmask»"
			next_hop = "«r.gateway»"
		} 
		«ENDFOR»		
		«ENDIF»
		'''		
	}
}