package it.csec.xtext.vsdl.Terraform

import org.eclipse.xtend.lib.annotations.Accessors

class Interface {
	@Accessors
	private var String networkid
	@Accessors
	private var String address

	new(String id, String address) {
		networkid = id
		this.address = address
	}
}