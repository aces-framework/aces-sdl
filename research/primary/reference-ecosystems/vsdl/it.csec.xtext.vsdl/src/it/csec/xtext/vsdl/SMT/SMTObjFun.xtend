package it.csec.xtext.vsdl.SMT

abstract class SMTObjFun<T> extends SMTObj<T> {
	public String funName
	public String[] funParams
	
	def abstract public void setFunName()

	def abstract public void setFunParams()
	
	new() {
		setFunName()
		setFunParams()
	}
	
	def public getFunName() {
		return funName
	}
	
	def public getFun() {
		return SMTObjUtils.generateFun(funName, funParams)
	}	
}