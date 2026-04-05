package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.Gateway

import org.smtlib.IExpr.IFcnExpr
import java.util.ArrayList

class SMTGateway extends SMTObjFun<Gateway> {
	def override public setFunName() {
		funName = "network.gateway.internet"
	}
	
	def override public setFunParams() {
		funParams = #["Int", "Int", "Bool"]
	}
	
	def override public ArrayList<IFcnExpr> compile(Gateway gw, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>((context.ttu / context.ttuStep) + 1)
		var k = 0

		if (gw.internet) {
			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				exprArr.add(
					k,
					context.efactory.fcn(
						context.efactory.symbol("="),
						context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i),
							context.efactory.symbol(name)),
						context.efactory.symbol("true")
					)
				)
				k++
			}
		}
		return exprArr
	}
}
