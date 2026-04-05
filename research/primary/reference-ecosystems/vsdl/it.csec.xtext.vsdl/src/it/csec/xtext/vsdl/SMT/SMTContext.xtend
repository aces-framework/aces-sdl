package it.csec.xtext.vsdl.SMT

import it.csec.xtext.generator.VsdlConsole

import org.smtlib.SMT
import org.smtlib.impl.Script
import org.smtlib.IExpr.IFactory

import java.util.ArrayList

import org.eclipse.xtend.lib.annotations.Accessors
import org.smtlib.command.C_declare_fun
import org.smtlib.command.C_assert

//import org.smtlib.command.C_assert

class SMTContext {
	@Accessors private SMT smt 
	@Accessors private IFactory efactory
	@Accessors private Script script
	@Accessors private int ttu
	@Accessors private int ttuStep
	
	@Accessors private ArrayList<String> scenelems
	@Accessors private ArrayList<String> nodes
	@Accessors private ArrayList<String> networks
	
	@Accessors private ArrayList<C_declare_fun> functions 
	//private ArrayList<C_declare_fun> functions 
	@Accessors private ArrayList<C_assert> iassertions
		
	@Accessors private VsdlConsole console
	
	// TODO: plugin configuration file
	@Accessors private String logic = "QF_AUFLIA"
	//@Accessors private int ttuStep = 5
		
	new(String name, int ttu, int ttuStep, VsdlConsole console) {
		smt = new SMT()
		efactory = smt.smtConfig.exprFactory
		script = new Script()
		this.ttu = ttu
		this.ttuStep = ttuStep
		
		functions = new ArrayList<C_declare_fun>()
		iassertions = new ArrayList<C_assert>()
		scenelems = new ArrayList<String>()
		nodes = new ArrayList<String>()
		networks = new ArrayList<String>()
		
		if (console !== null) {
			this.console = console
		} else {
			this.console = new VsdlConsole(name)
		}
	}
	
//	def getFunctions() {
//		return this.functions
//	}
	
	def addFunction(C_declare_fun f) {
		var i = 0
		var flag = false
		
		while (! flag && i < functions.size) {
			flag = f.symbol.toString.equals(functions.get(i).symbol.toString)
			i++	
		}
		
		if (! flag) {
			functions.add(f)
		} 
	}
}