package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.UpdateTriggerConstraint

import org.smtlib.IExpr.IFcnExpr
import org.eclipse.emf.ecore.EObject
import java.util.ArrayList

class SMTUpdateTriggerConstraint extends SMTObj<UpdateTriggerConstraint> {
	def override public ArrayList<IFcnExpr> compile(UpdateTriggerConstraint constraint, String name, SMTContext context) {
		return new SMTObjFactory(constraint as EObject).compile(name, context)
	}
}
