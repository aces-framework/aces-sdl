package it.csec.xtext.vsdl.SMT

import it.csec.xtext.VsdlToken

import it.csec.xtext.vsdl.At

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList
import java.util.Collections


class SMTAt extends SMTObj<At> {
	def override public ArrayList<IFcnExpr> compile(At at, String name, SMTContext context) {
		//var exprArr = new ArrayList<IFcnExpr>(Collections.nCopies((((context.ttu / context.ttuStep) + 1) * 2) + 1, null))
		var exprArr = new ArrayList<IFcnExpr>(Collections.nCopies(((context.ttu / context.ttuStep) + 2), null))
		
		var k = 1
		
		var symbol = ">="
		if (at.op == VsdlToken.ATMOST) {
			symbol = "<="
		}

		// TODO: remove declare_fun here!
		/* context.script.commands().add(new C_declare_fun(
		  		context.efactory.symbol(at.variable),
		  		new java.util.LinkedList<ISort>(),
		  		context.smt.smtConfig.sortFactory.createSortExpression(context.efactory.symbol("Int"))
		 )) */
		context.addFunction(SMTObjUtils.generateFun(at.variable, "Int"))		 

		exprArr.set(
			0,
			context.efactory.fcn(
				context.efactory.symbol(symbol),
				context.efactory.symbol(at.variable),
				new SMTTimeExpr(at.texp).compile
			)
		)

		for (var i = 0; i <= context.ttu; i += context.ttuStep) {
			exprArr.set(
				k,
				context.efactory.fcn(
					context.efactory.symbol("<="),
					context.efactory.symbol(at.variable),
					context.efactory.numeral(i)
				)
			)
		/* 	exprArr.set(
				k + (context.ttu / context.ttuStep) + 1,
				context.efactory.fcn(
					context.efactory.symbol(">="),
					context.efactory.symbol(at.variable),					
					context.efactory.numeral(i)
				)
			) */
			k++
		}
		
		return exprArr
	}
}