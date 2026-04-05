package it.csec.xtext.vsdl.Terraform

import org.eclipse.xtend.lib.annotations.Accessors

class Flavor {
	@Accessors
	private int vcpu
	@Accessors
	private int ram
	@Accessors
	private int disk
}