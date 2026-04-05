package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.OSFamily

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList
import it.csec.xtext.VsdlResources

class SMTOSFamily extends SMTObj<OSFamily> {
	/* def override public setFunName() {
		funName = "node.osfamily"
	}
	
	def override public setFunParams() {
		funParams = #["Int", "Int", "Int"]
	} */
	
	def override public ArrayList<IFcnExpr> compile(OSFamily os, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>((context.ttu / context.ttuStep) + 1)
		var k = 0

		var fl = VsdlResources.getOssFamilyIds(os.family.substring(1, os.family.length - 1))

		if (fl.size == 1) {
			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				exprArr.add(k, context.efactory.fcn(
					context.efactory.symbol("="),
					context.efactory.fcn(context.efactory.symbol(new SMTOS().funName), context.efactory.numeral(i), context.efactory.symbol(name)),
					context.efactory.numeral(fl.get(0))
				))
				k++
			} 			
		} else {
			// or !!
			var orExpr = new ArrayList<IFcnExpr>(fl.size)

			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				var h = 0
				for (int f : fl) {
					orExpr.add(h, context.efactory.fcn(
						context.efactory.symbol("="),
						context.efactory.fcn(context.efactory.symbol(new SMTOS().funName), context.efactory.numeral(i), 
							context.efactory.symbol(name)
						),
						context.efactory.numeral(f)
					))			
					h++	
				}
				exprArr.add(k, context.efactory.fcn(context.efactory.symbol("or"), orExpr))
				orExpr.clear
				k++
			} 				
		}

		return exprArr
	}
}