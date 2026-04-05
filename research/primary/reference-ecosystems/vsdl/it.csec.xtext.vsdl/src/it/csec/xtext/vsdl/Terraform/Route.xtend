package it.csec.xtext.vsdl.Terraform

import org.eclipse.xtend.lib.annotations.Accessors

class Route {
	@Accessors
	private var String address
	@Accessors
	private var int netmask
	@Accessors
	private var String gateway
	@Accessors
	private var String name
	
	
	new(String name, String address, int netmask, String gateway) {
		this.name = name
		this.address = address
		this.netmask = netmask
		this.gateway = gateway
	}
}