package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.TimeExpr
import it.csec.xtext.vsdl.PlusMinus
import it.csec.xtext.vsdl.Multiplication

import it.csec.xtext.VsdlToken
import org.smtlib.SMT
import org.smtlib.IExpr.IFactory
import org.smtlib.IExpr

class SMTTimeExpr {
	SMT smt = new SMT()
	IFactory efactory = smt.smtConfig.exprFactory
	TimeExpr t

	new(TimeExpr t) {
		this.t = t
	}

	def IExpr compile() {
		switch this.t {
			PlusMinus: {
				var symbol = "+"
				if (t.op == VsdlToken.MINUS) {
					symbol = "-"
				}

				return efactory.fcn(
					efactory.symbol(symbol),
					new SMTTimeExpr(t.left).compile,
					new SMTTimeExpr(t.right).compile
				)
			}
			Multiplication: {
				return efactory.fcn(
					efactory.symbol("*"),
					new SMTTimeExpr(t.left).compile,
					new SMTTimeExpr(t.right).compile
				)
			}
			default: {
				if (t.interval !== null) {
  					return efactory.numeral(t.interval.value)
				} else {
					if (t.variable !== null) {
						return efactory.symbol(t.variable)
					}
				}

				return efactory.symbol("oops! : " + t.getClass.getSimpleName)
			}
		}
	}
}