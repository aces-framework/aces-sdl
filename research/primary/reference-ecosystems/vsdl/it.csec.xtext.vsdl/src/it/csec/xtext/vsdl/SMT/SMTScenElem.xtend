package it.csec.xtext.vsdl.SMT

import org.smtlib.IExpr.IFcnExpr

import org.eclipse.emf.common.util.EList;
import org.eclipse.emf.ecore.EObject
import java.util.ArrayList

abstract class SMTScenElem<S,T> extends SMTObj<T> {	
	 def public EList<S> getConstraints(T elem)

	 def override public ArrayList<IFcnExpr> compile(T elem, String name, SMTContext context) {
	 	var exprArrList = new ArrayList<IFcnExpr>

	 	for (S constraint : elem.constraints) {
			exprArrList.addAll(new SMTObjFactory(constraint as EObject).compile(name, context))
 		} 		
	 	
	 	return exprArrList
	 }
}