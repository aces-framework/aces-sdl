package it.csec.xtext.vsdl.SMT

import it.csec.xtext.VsdlToken

import it.csec.xtext.vsdl.AndOr

import org.smtlib.IExpr.IFcnExpr
import java.util.ArrayList
import java.util.Collections

class SMTAndOr extends SMTObj<AndOr> {
	def override public ArrayList<IFcnExpr> compile(AndOr obj, String name, SMTContext context) {
		var ArrayList<IFcnExpr> exprArr 
		var ArrayList<IFcnExpr> leftArr
		var ArrayList<IFcnExpr> rightArr
		var k = 0

		var symbol = "and"
		if (obj.op == VsdlToken.OR) {
			symbol = "or"
		} 

		leftArr = new SMTObjFactory(obj.left).compile(name, context)
		rightArr = new SMTObjFactory(obj.right).compile(name, context)


		if (leftArr.size > ((context.ttu / context.ttuStep) + 1)) {
			//exprArr = new ArrayList<IFcnExpr>(Collections.nCopies((((context.ttu / context.ttuStep) + 1) * 2) + 1, null)) 
			exprArr = new ArrayList<IFcnExpr>(Collections.nCopies(((context.ttu / context.ttuStep) + 2), null)) 
			
			exprArr.set(
				0,
				context.efactory.fcn(context.efactory.symbol(symbol), leftArr.get(0), rightArr.get(0))
			)
			k = 1

			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				exprArr.set(
					k,
					context.efactory.fcn(context.efactory.symbol(symbol), leftArr.get(k), rightArr.get(k))
				)
				/* exprArr.set(
					k + (context.ttu / context.ttuStep) + 1,
					context.efactory.fcn(context.efactory.symbol(symbol), leftArr.get(k + (context.ttu / context.ttuStep) + 1),
						rightArr.get(k + (context.ttu / context.ttuStep) + 1))
				) */
				k++
			}
		} else {
			exprArr = new ArrayList<IFcnExpr>((context.ttu / context.ttuStep) + 1)
			
			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				exprArr.add(
					k,
					context.efactory.fcn(context.efactory.symbol(symbol), leftArr.get(k), rightArr.get(k))
				)
				k++
			}
		}
						
		return exprArr
	}
}