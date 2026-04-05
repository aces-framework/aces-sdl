package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.Model
import it.csec.xtext.vsdl.ScenElem

import org.smtlib.impl.Script
import org.smtlib.IExpr.IFcnExpr
import org.smtlib.command.C_declare_fun
import org.smtlib.command.C_assert
import org.smtlib.command.C_set_logic
import org.smtlib.SMT
import org.smtlib.command.C_check_sat
import org.smtlib.command.C_get_model
import org.smtlib.command.C_exit

import java.util.ArrayList
import org.smtlib.command.C_get_value
import it.csec.xtext.vsdl.impl.NodeImpl

class SMTModel extends SMTObj<Model> {	
	private Model model
		
	def override public ArrayList<IFcnExpr> compile(Model model, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>

		for (ScenElem element : model.elements) {
			exprArr.addAll(new SMTObjFactory(element).compile(element.name, context))
		}

		return exprArr
	}
	
	new() {}
	
	new(Model model) {
		this.model = model
	}
	
	def public compileScript(SMTContext context) {
		var efactory = new SMT().smtConfig.exprFactory
		var getvalues = new ArrayList<C_get_value>()
		
		var script = new Script()
		
		if (model === null) {
			return null
		}
			
		// set logic
		script.commands().add(new C_set_logic(efactory.symbol(context.logic)))
		
		// main functions
		for (ScenElem element : model.elements) {	
			context.scenelems.add(element.name)
			
			if (element instanceof NodeImpl) {
				context.nodes.add(element.name)
			} else {
				context.networks.add(element.name)
			}
					
		 	script.commands().add(SMTObjUtils.generateFun(element.name, "Int"))
		 	getvalues.addAll(SMTObjUtils.generateGetValues(element, context.ttu, context.ttuStep))
		}
			
		// TODO: remove these function declarations from here (check how we can handle elements which require multiple functions)
		script.commands().add(SMTObjUtils.generateFun("network.address", "Int", "Int", "Int"))
		script.commands().add(SMTObjUtils.generateFun("network.netmask", "Int", "Int", "Int"))
			
		// TODO: network.node.address, how can we handle this?
	 	for (String n : context.networks) {
			for (String e : context.scenelems) {
				//if (! e.equals(n)) {
					for (var i = 0; i <= context.ttu; i += context.ttuStep) {
						getvalues.add(SMTObjUtils.generateGetValue(new SMTIP().funName, i, n, e))
					}
				//}
			}
		} 
		
		// obj functions
		for (C_declare_fun fun : SMTObjUtils.generateElementsFun()) {
			script.commands().add(fun)
		}
		
		var exprArr = new SMTObjFactory(model).compile(model.name, context)
		
		// vars functions
		for (C_declare_fun fun: context.functions) {
		 	script.commands().add(fun)			
		}
				
		// assertions
		for (IFcnExpr expr: exprArr) {			
			script.commands().add(new C_assert(expr))
		} 
				
		for (C_assert a: context.iassertions) {	
			script.commands().add(a)
		} 
		
		// check sat and get model
		script.commands().add(new C_check_sat())
		script.commands().add(new C_get_model())		
		
		// get values (get-value ((node.cpu 20 node1)))
		for (C_get_value getvalue: getvalues) {
			script.commands.add(getvalue)
		}
		
		script.commands().add(new C_exit())
		
		return script
	}
}
