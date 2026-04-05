package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.Flavour

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList
import it.csec.xtext.VsdlResources

class SMTFlavour extends SMTObj<Flavour> {
	/* def override public setFunName() {
		funName = "node.flavour"
	}
	
	def override public setFunParams() {
		funParams = #["Int", "Int", "Int"]
	} */
	
	def override public ArrayList<IFcnExpr> compile(Flavour flavour, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>((context.ttu / context.ttuStep) + 1)
		var k = 0
		
		var f = VsdlResources.getFlavor(flavour.profile)
		var flExpr = new ArrayList<IFcnExpr>(3)		
		if (f !== null) {
			// name=cirros256, vcpus=1, ram=256, disk=0, ephemeral=0, swap=0, rxtx_factor=1.0 
			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				flExpr.add(0, context.efactory.fcn(
					context.efactory.symbol("="),
					context.efactory.fcn(context.efactory.symbol(new SMTVCPU().funName), context.efactory.numeral(i), 
						context.efactory.symbol(name)
					),
					context.efactory.numeral(f.vcpus)
				))			

				// GB
				flExpr.add(1, context.efactory.fcn(
					context.efactory.symbol("="),
					context.efactory.fcn(context.efactory.symbol(new SMTDisk().funName), context.efactory.numeral(i), 
						context.efactory.symbol(name)
					),
					context.efactory.numeral(f.disk * 1024)
				))			

				// MB
				flExpr.add(1, context.efactory.fcn(
					context.efactory.symbol("="),
					context.efactory.fcn(context.efactory.symbol(new SMTRam().funName), context.efactory.numeral(i), 
						context.efactory.symbol(name)
					),
					context.efactory.numeral(f.ram)
				))			
				
				exprArr.add(k, context.efactory.fcn(context.efactory.symbol("and"), flExpr))
				flExpr.clear
				k++
			} 					
		} else {
			// dummy flavor ??
			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				flExpr.add(0, context.efactory.fcn(
					context.efactory.symbol(">"),
					context.efactory.fcn(context.efactory.symbol(new SMTVCPU().funName), context.efactory.numeral(i), 
						context.efactory.symbol(name)
					),
					context.efactory.numeral(0)
				))			

				flExpr.add(1, context.efactory.fcn(
					context.efactory.symbol(">"),
					context.efactory.fcn(context.efactory.symbol(new SMTDisk().funName), context.efactory.numeral(i), 
						context.efactory.symbol(name)
					),
					context.efactory.numeral(0)
				))			

				flExpr.add(1, context.efactory.fcn(
					context.efactory.symbol(">"),
					context.efactory.fcn(context.efactory.symbol(new SMTRam().funName), context.efactory.numeral(i), 
						context.efactory.symbol(name)
					),
					context.efactory.numeral(0)
				))			
				
				exprArr.add(k, context.efactory.fcn(context.efactory.symbol("and"), flExpr))
				flExpr.clear
				k++
			} 					
		}
		
		return exprArr
	}
}