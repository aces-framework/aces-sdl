package it.csec.xtext.vsdl.SMT

import org.smtlib.ISort
import org.smtlib.SMT
import org.smtlib.command.C_declare_fun
// import org.smtlib.command.C_set_logic

import java.util.ArrayList
import org.smtlib.command.C_get_value
import org.smtlib.IExpr
import it.csec.xtext.vsdl.Node
import it.csec.xtext.vsdl.ScenElem
import it.csec.xtext.vsdl.Network

class SMTObjUtils {
	def static public generateFun(String name, String... args) {
		var smt = new SMT()
		var efactory = smt.smtConfig.exprFactory

		var inputParam = new java.util.LinkedList<ISort>
		
		for (var i = 0; i < args.size - 1; i++) {
			inputParam.add(smt.smtConfig.sortFactory.createSortExpression(efactory.symbol(args.get(i))))
		}
		
		return new C_declare_fun(efactory.symbol(name), inputParam,
				smt.smtConfig.sortFactory.createSortExpression(efactory.symbol(args.get(args.size - 1))))
	}
	
	def static public generateElementsFun() {
		var functions = new ArrayList<C_declare_fun>()
		
		// node
		//functions.add(new SMTCPU().fun)
		functions.add(new SMTVCPU().fun)
		functions.add(new SMTDisk().fun)
		functions.add(new SMTOS().fun)
		functions.add(new SMTRam().fun)
		// network	
		functions.add(new SMTGateway().fun)
		functions.add(new SMTIP().fun)
		
		return functions
	}
	
	def static generateGetValue(String objFunName, int time, String... args) {
		var efactory = new SMT().smtConfig.exprFactory
		var param = new java.util.LinkedList<IExpr>
		
		var e = new ArrayList<IExpr>
		
		e.add(efactory.numeral(time))

		var i = 0
		for (String a : args) {
			e.add(efactory.symbol(args.get(i)))
			i++
		}
		
		var f = efactory.fcn(efactory.symbol(objFunName), e)
		param.add(f)
		
		return new C_get_value(param)
	}
	
	def static generateGetValues(ScenElem elem, int ttu, int ttuStep) {
		var getvalues = new ArrayList<C_get_value>()
		
		for (var i = 0; i <= ttu; i += ttuStep) {
			 if (elem instanceof Node) {
				 //getvalues.add(generateGetValue(new SMTCPU().funName, i, elem.name))
				 getvalues.add(generateGetValue(new SMTVCPU().funName, i, elem.name))
				 getvalues.add(generateGetValue(new SMTDisk().funName, i, elem.name)) 			 	
 				 getvalues.add(generateGetValue(new SMTOS().funName, i, elem.name))
 				 getvalues.add(generateGetValue(new SMTRam().funName, i, elem.name)) 			 	 			 	
			 }			
		}
		
		for (var i = 0; i <= ttu; i += ttuStep) {
			 if (elem instanceof Network) {
				 getvalues.add(generateGetValue(new SMTGateway().funName, i, elem.name))
				 getvalues.add(generateGetValue("network.address", i, elem.name))
				 getvalues.add(generateGetValue("network.netmask", i, elem.name))
				 // handle network.node.address
				 //getvalues.add(generateGetValue(new SMTIP().funName, i, elem.name))
			 }			
		}
		
		return getvalues
	}
}