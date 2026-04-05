package it.csec.xtext.vsdl.SMT

//import it.csec.xtext.VsdlToken
//import it.csec.xtext.vsdl.CPU
//import it.csec.xtext.vsdl.CPUFrequency

//import org.smtlib.IExpr.IFcnExpr

//import java.util.ArrayList

/* class SMTCPU extends SMTObjFun<CPU> {	
	def override public setFunName() {
		funName = "node.cpu"
	}
	
	def override public setFunParams() {
		funParams = #["Int", "Int", "Int"]
	}
	
	def override public ArrayList<IFcnExpr> compile(CPU cpu, String name, SMTContext context) {
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
					case VsdlToken.FASTER: symbol = ">"
					case VsdlToken.SLOWER: symbol = "<"
				}

				exprArr.add(
					k,
					context.efactory.fcn(
						context.efactory.symbol(symbol),
						context.efactory.fcn(context.efactory.symbol("node.cpu"), context.efactory.numeral(i),
							context.efactory.symbol(name)),
						context.efactory.numeral(compileCPUFrequency(cpu.value))
					)
				)
			}
			k++
		}

		return exprArr
	}

	def compileCPUFrequency(CPUFrequency frequency) {
		switch (frequency.unit) {
			case VsdlToken.MHZ: return frequency.value
			case VsdlToken.GHZ: return frequency.value * 10000
			case VsdlToken.THZ: return frequency.value * 100000 * 10000
			default: return 0
		}
	}
} */
