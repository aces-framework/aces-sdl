package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.Node
import it.csec.xtext.vsdl.NodeConstraint

import org.eclipse.emf.common.util.EList;

class SMTNode extends SMTScenElem<NodeConstraint, Node> {
		def public override EList<NodeConstraint> getConstraints(Node elem) {
			return elem.constraints
		}
}
