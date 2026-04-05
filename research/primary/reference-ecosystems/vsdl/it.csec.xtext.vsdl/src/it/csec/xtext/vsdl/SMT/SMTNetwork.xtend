	package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.Network
import it.csec.xtext.vsdl.NetworkConstraint

import org.eclipse.emf.common.util.EList;
import org.smtlib.command.C_assert

class SMTNetwork extends SMTScenElem<NetworkConstraint, Network> {
	def public static getIAssertions(String name, SMTContext context) {
		for (var i = 0; i < context.scenelems.size; i++) {
			for (var k = i; k < context.scenelems.size; k++) {
				if (context.scenelems.get(i) != context.scenelems.get(k)) {

					for (var h = 0; h <= context.ttu; h += context.ttuStep) {
						var n1 = context.efactory.fcn(
							context.efactory.symbol("network.node.address"),
							context.efactory.numeral(h),
							context.efactory.symbol(name),
							context.efactory.symbol(context.scenelems.get(i))
						)
						
						var n2 = context.efactory.fcn(
							context.efactory.symbol("network.node.address"),
							context.efactory.numeral(h),
							context.efactory.symbol(name),
							context.efactory.symbol(context.scenelems.get(k))
						)

						context.iassertions.add(
							new C_assert(
								context.efactory.fcn(
									context.efactory.symbol("=>"),
									context.efactory.fcn(
										context.efactory.symbol("="),
										n1,
										n2
									),
									context.efactory.fcn(
										context.efactory.symbol("="),
										n1,
										context.efactory.numeral(0)
									)
								)
							)
						)
					}
				}
			}
		}
	}

	def public override EList<NetworkConstraint> getConstraints(Network elem) {
		return elem.constraints
	}
}
