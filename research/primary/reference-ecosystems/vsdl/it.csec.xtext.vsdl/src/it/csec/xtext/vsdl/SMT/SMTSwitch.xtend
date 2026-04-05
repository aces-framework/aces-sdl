package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.Switch

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList
import java.util.Collections


class SMTSwitch extends SMTObj<Switch> {
	def override public ArrayList<IFcnExpr> compile(Switch sw, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>(Collections.nCopies(((context.ttu / context.ttuStep) + 2), null))
		
		var k = 1
		context.functions.add(SMTObjUtils.generateFun(sw.variable, "Int"))		 

		exprArr.set(
			0,
			context.efactory.fcn(
				context.efactory.symbol("="),
				context.efactory.symbol(sw.variable),
				new SMTTimeExpr(sw.texp).compile
			)
		)

		for (var i = 0; i <= context.ttu; i += context.ttuStep) {
			exprArr.set(k, context.efactory.fcn(
				context.efactory.symbol("="),
				context.efactory.fcn(
					context.efactory.symbol("mod"),
					context.efactory.fcn(
						context.efactory.symbol("div"),
						context.efactory.numeral(i),
						context.efactory.symbol(sw.variable)
					),
					context.efactory.numeral(2)
				),
				context.efactory.numeral(0)
			))
			k++
		}		
		return exprArr
	}
}