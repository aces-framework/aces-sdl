package it.csec.xtext.vsdl.SMT

import org.smtlib.IExpr.IFcnExpr
import org.eclipse.emf.ecore.EObject
import java.util.ArrayList
import it.csec.xtext.vsdl.impl.SwitchImpl

abstract class SMTConstraint<T> extends SMTObj<T> {
	def public boolean hasTriggerConstraint(T constraint)
	
	def public EObject getTriggerConstraint(T constraint)
	
	def public EObject getConstraint(T constraint)
	
	def public override ArrayList<IFcnExpr> compile(T constraint, String name, SMTContext context) {
	//	try {
			if (! this.hasTriggerConstraint(constraint)) {
				return new SMTObjFactory(constraint as EObject).compile(name, context)
			} else {
				var k = 1
								
				var constrArr = new SMTObjFactory(this.getTriggerConstraint(constraint)).compile(name, context)
				var exprArr = new SMTObjFactory(this.getConstraint(constraint)).compile(name, context)

				var symbol = "=>"				
				if (this.getTriggerConstraint(constraint) instanceof SwitchImpl) {
					symbol = "="
				}
				
				for (var i = 0; i <= context.ttu; i += context.ttuStep) {					
					constrArr.set(
						k,
						context.efactory.fcn(
							context.efactory.symbol(symbol),
							constrArr.get(k),
							exprArr.get(k - 1)
						)
					)
					
					k++
				}

				return constrArr
			}
//		} catch (Exception ex) {
//			return this.unsupportedObj(constraint as EObject, ttu, ttuStep)
//		}		
	}
}
