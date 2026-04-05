package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.IP

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList
import java.net.InetAddress

class SMTIP extends SMTObjFun<IP> {
	def override public setFunName() {
		funName = "network.node.address"
	}
	
	def override public setFunParams() {
		funParams = #["Int", "Int", "Int", "Int"]
	}
	
	def override public ArrayList<IFcnExpr> compile(IP ip, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>((context.ttu / context.ttuStep) + 1)
		var k = 0

		if (ip.op == "connected") {
			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				exprArr.add(k, context.efactory.fcn(
					context.efactory.symbol(">"),
					context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i),
						context.efactory.symbol(name), context.efactory.symbol(ip.id.name)),
					context.efactory.numeral(0)
				))
			}
		} else {
			var bAddr = InetAddress.getByName(
				ip.address.octet1 + "." + ip.address.octet2 + "." + ip.address.octet3 + "." + ip.address.octet4
			).address

			var addr = (Byte.toUnsignedLong(bAddr.get(0)) * 16777216).bitwiseOr(Byte.toUnsignedLong(bAddr.get(1)) *
				65536).bitwiseOr(Byte.toUnsignedLong(bAddr.get(2)) * 256).bitwiseOr(Byte.toUnsignedLong(bAddr.get(3)))

			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				exprArr.add(k, context.efactory.fcn(
					context.efactory.symbol("="),
					context.efactory.fcn(context.efactory.symbol(funName), context.efactory.numeral(i),
						context.efactory.symbol(name), context.efactory.symbol(ip.id.name)),
					context.efactory.numeral(addr)
				))
			}
		}
		return exprArr
	}
}