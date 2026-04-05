package it.csec.xtext.vsdl.SMT

import it.csec.xtext.VsdlToken
import it.csec.xtext.vsdl.Disk
import it.csec.xtext.vsdl.DiskSize

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList

class SMTDisk extends SMTObjFun<Disk> {
	def override public setFunName() {
		funName = "node.disk"
	}
	
	def override public setFunParams() {
		funParams = #["Int", "Int", "Int"]
	}
	
	def override public ArrayList<IFcnExpr> compile(Disk disk, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>((context.ttu / context.ttuStep) + 1)
		var symbol = "="
		var k = 0

		for (var i = 0; i <= context.ttu; i += context.ttuStep) {
			if (disk.sameas) {
				exprArr.add(
					k,
					context.efactory.fcn(context.efactory.symbol(symbol),
						context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i), context.efactory.symbol(name)),
						context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i), context.efactory.symbol(disk.id.name)))
				)
			} else {
				switch (disk.op) {
					case VsdlToken.LARGER: symbol = ">"
					case VsdlToken.SMALLER: symbol = "<"
				}

				exprArr.add(
					k,
					context.efactory.fcn(
						context.efactory.symbol(symbol),
						context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i), context.efactory.symbol(name)),
						context.efactory.numeral(compileDiskSize(disk.value))
					)
				)
			}
			k++
		}

		return exprArr
	}

	def compileDiskSize(DiskSize size) {					
		switch (size.unit) {
			// case VsdlToken.BYTE : return size.value
			// case VsdlToken.KILOBYTE : return size.value
			case VsdlToken.MEGABYTE: return size.value
			case VsdlToken.GIGABYTE: return size.value * 1024
			case VsdlToken.TERABYTE: return size.value * 1048576
			default: return 0
		}
	}
}