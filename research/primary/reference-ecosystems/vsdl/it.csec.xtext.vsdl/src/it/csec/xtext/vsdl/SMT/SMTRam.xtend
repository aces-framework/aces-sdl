package it.csec.xtext.vsdl.SMT

import it.csec.xtext.VsdlToken
import it.csec.xtext.vsdl.Ram
import it.csec.xtext.vsdl.RamSize

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList

class SMTRam extends SMTObjFun<Ram> {
	def override public setFunName() {
		funName = "node.ram"
	}
	
	def override public setFunParams() {
		funParams = #["Int", "Int", "Int"]
	}
	
	def override public ArrayList<IFcnExpr> compile(Ram ram, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>((context.ttu / context.ttuStep) + 1)
		var symbol = "="
		var k = 0

		for (var i = 0; i <= context.ttu; i += context.ttuStep) {
			if (ram.sameas) {
				exprArr.add(
					k,
					context.efactory.fcn(context.efactory.symbol(symbol),
						context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i), context.efactory.symbol(name)),
						context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i), context.efactory.symbol(ram.id.name)))
				)
			} else {
				switch (ram.op) {
					case VsdlToken.LARGER: symbol = ">"
					case VsdlToken.SMALLER: symbol = "<"
				}

				exprArr.add(
					k,
					context.efactory.fcn(
						context.efactory.symbol(symbol),
						context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i), context.efactory.symbol(name)),
						context.efactory.numeral(compileRamSize(ram.value))
					)
				)
			}
			k++
		}

		return exprArr
	}

	def compileRamSize(RamSize size) {					
		switch (size.unit) {
			// case VsdlToken.BYTE : return size.value
			// case VsdlToken.KILOBYTE : return size.value
			case VsdlToken.MEGABYTE: return size.value
			case VsdlToken.GIGABYTE: return size.value * 1024
			//case VsdlToken.TERABYTE: return size.value * 1048576
			default: return 0
		}
	}
}