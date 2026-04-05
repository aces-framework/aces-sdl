package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.OS

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList
import it.csec.xtext.VsdlResources

class SMTOS extends SMTObjFun<OS> {
	def override public setFunName() {
		funName = "node.os"
	}
	
	def override public setFunParams() {
		funParams = #["Int", "Int", "Int"]
	}
	
	def override public ArrayList<IFcnExpr> compile(OS os, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>((context.ttu / context.ttuStep) + 1)
		var k = 0
		
		var int id
		
		try {
			// remove double quotes!
			id = VsdlResources.getOsId(os.version.substring(1, os.version.length - 1))
		} catch (Exception e) {
			id = 0
		}

		for (var i = 0; i <= context.ttu; i += context.ttuStep) {
			exprArr.add(k, context.efactory.fcn(
				context.efactory.symbol("="),
				context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i), context.efactory.symbol(name)),
				context.efactory.numeral(id)
			))
			k++
		}

		// 0 if not found..
		return exprArr
	}
}