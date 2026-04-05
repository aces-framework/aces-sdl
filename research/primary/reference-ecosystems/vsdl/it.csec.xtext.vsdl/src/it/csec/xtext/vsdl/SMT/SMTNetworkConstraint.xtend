package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.NetworkConstraint

class SMTNetworkConstraint extends SMTConstraint<NetworkConstraint> {
	def public override hasTriggerConstraint(NetworkConstraint constraint) {
		return constraint.networktriggerconstraint !== null
	}

	def public override getTriggerConstraint(NetworkConstraint constraint) {
		return constraint.networktriggerconstraint
	}
	
	def public override getConstraint(NetworkConstraint constraint) {
		return constraint.networkconstraint
	}
}