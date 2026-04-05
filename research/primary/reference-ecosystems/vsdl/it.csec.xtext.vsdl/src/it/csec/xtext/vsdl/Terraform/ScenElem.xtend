package it.csec.xtext.vsdl.Terraform

import org.eclipse.xtend.lib.annotations.Accessors

abstract class ScenElem {
	@Accessors
	private String name
	@Accessors
	private String scenario
	@Accessors
	private int ttuStep
}