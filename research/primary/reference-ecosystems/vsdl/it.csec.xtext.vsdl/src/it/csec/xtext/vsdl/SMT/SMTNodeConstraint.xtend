package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.NodeConstraint

class SMTNodeConstraint extends SMTConstraint<NodeConstraint> {
	def public override hasTriggerConstraint(NodeConstraint constraint) {
		return constraint.triggerconstraint !== null
	}

	def public override getTriggerConstraint(NodeConstraint constraint) {
		return constraint.triggerconstraint
	}
	
	def public override getConstraint(NodeConstraint constraint) {
		return constraint.nodeconstraint
	}
}