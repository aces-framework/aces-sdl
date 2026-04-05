package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.Not

import org.smtlib.IExpr.IFcnExpr
import java.util.ArrayList
import java.util.Collections

class SMTNot extends SMTObj<Not> {
	def override public ArrayList<IFcnExpr> compile(Not obj, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>
		var rightArr = new ArrayList<IFcnExpr>
		var k = 0
		
		rightArr = new SMTObjFactory(obj.constraint).compile(name, context)
		
		if (rightArr.size > ((context.ttu / context.ttuStep) + 1)) {			
			//exprArr = new ArrayList<IFcnExpr>(Collections.nCopies((((context.ttu / context.ttuStep) + 1) * 2) + 1, null))
			exprArr = new ArrayList<IFcnExpr>(Collections.nCopies(((context.ttu / context.ttuStep) + 2), null))
			
			exprArr.set(
				0,
				context.efactory.fcn(context.efactory.symbol("not"), rightArr.get(0))
			)
			k = 1

			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				exprArr.set(
					k,
					context.efactory.fcn(context.efactory.symbol("not"), rightArr.get(k))
				)
				/* exprArr.set(
					k + (context.ttu / context.ttuStep) + 1,
					context.efactory.fcn(context.efactory.symbol("not"),
						rightArr.get(k + (context.ttu / context.ttuStep) + 1))
				) */
				
				k++
			}
		} else {			
			exprArr = new ArrayList<IFcnExpr>((context.ttu / context.ttuStep) + 1)
			
			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				exprArr.add(
					k,
					context.efactory.fcn(context.efactory.symbol("not"), rightArr.get(k))
				)
				k++
			}
		}
						
		return exprArr
	}
}