package it.csec.xtext.vsdl.SMT

import it.csec.xtext.VsdlToken
import it.csec.xtext.vsdl.VCPU

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList

 class SMTVCPU extends SMTObjFun<VCPU> {	
	def override public setFunName() {
		funName = "node.vcpu"
	}
	
	def override public setFunParams() {
		funParams = #["Int", "Int", "Int"]
	}
	
	def override public ArrayList<IFcnExpr> compile(VCPU cpu, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>((context.ttu / context.ttuStep) + 1)
		var symbol = "="
		var k = 0

		for (var i = 0; i <= context.ttu; i += context.ttuStep) {
			if (cpu.sameas) {
				exprArr.add(
					k,
					context.efactory.fcn(context.efactory.symbol(symbol),
						context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i),
							context.efactory.symbol(name)),
						context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i),
							context.efactory.symbol(cpu.id.name)))
				)
			} else {
				switch (cpu.op) {
					case VsdlToken.GREATER: symbol = ">"
					case VsdlToken.LESS: symbol = "<"
				}

				exprArr.add(
					k,
					context.efactory.fcn(
						context.efactory.symbol(symbol),
						context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i),
							context.efactory.symbol(name)),
						context.efactory.numeral(cpu.value)
					)
				)
			}
			k++
		}

		return exprArr
	}
} 