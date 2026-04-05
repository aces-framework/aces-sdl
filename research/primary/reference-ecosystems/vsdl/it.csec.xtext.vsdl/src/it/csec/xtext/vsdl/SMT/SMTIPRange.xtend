package it.csec.xtext.vsdl.SMT

import it.csec.xtext.vsdl.IPRange

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList
import java.net.InetAddress

class SMTIPRange extends SMTObj<IPRange> {
	def override public ArrayList<IFcnExpr> compile(IPRange ipr, String name, SMTContext context) {
		var exprArr = new ArrayList<IFcnExpr>(1) //(context.ttu / context.ttuStep) + 1)
		//var k = 0

		var bAddr = InetAddress.getByName(
			ipr.range.address.octet1 + "." + ipr.range.address.octet2 + "." + ipr.range.address.octet3 + "." +
				ipr.range.address.octet4
		).address

		var addr = (Byte.toUnsignedLong(bAddr.get(0)) * 16777216).bitwiseOr(Byte.toUnsignedLong(bAddr.get(1)) * 65536).
			bitwiseOr(Byte.toUnsignedLong(bAddr.get(2)) * 256).bitwiseOr(Byte.toUnsignedLong(bAddr.get(3)))

		var netmask = 0xffffffff << (32 - ipr.range.bitmask)

		var first = addr.bitwiseAnd(netmask)
		var last = addr.bitwiseOr(netmask.bitwiseNot)

		for (String elem : context.scenelems) {
			for (var i = 0; i <= context.ttu; i += context.ttuStep) {
				var no = context.efactory.fcn(
					context.efactory.symbol("="),
					context.efactory.fcn(
						context.efactory.symbol("network.node.address"),
						context.efactory.numeral(i),
						context.efactory.symbol(name),
						context.efactory.symbol(elem)												
					),
					context.efactory.numeral(0)
				)

				var s = context.efactory.fcn(
					context.efactory.symbol(">"),
					context.efactory.fcn(
						context.efactory.symbol("network.node.address"),
						context.efactory.numeral(i),
						context.efactory.symbol(name),
						context.efactory.symbol(elem)												
					),
					context.efactory.numeral(first)
				)

				var e = context.efactory.fcn(
					context.efactory.symbol("<"),
					context.efactory.fcn(
						context.efactory.symbol("network.node.address"),
						context.efactory.numeral(i),
						context.efactory.symbol(name),
						context.efactory.symbol(elem)												
					),
					context.efactory.numeral(last)
				)

				exprArr.add(0, context.efactory.fcn(
					context.efactory.symbol("or"),
					no,
					context.efactory.fcn(context.efactory.symbol("and"), s, e)
				))
			}
		}
		
		for (var i = 0; i <= context.ttu; i += context.ttuStep) {
			exprArr.add(0, context.efactory.fcn(
				context.efactory.symbol("="),
				context.efactory.fcn(
					context.efactory.symbol("network.address"),
					context.efactory.numeral(i),
					context.efactory.symbol(name)
				),
				context.efactory.numeral(addr)
			))

			exprArr.add(0, context.efactory.fcn(
				context.efactory.symbol("="),
				context.efactory.fcn(
					context.efactory.symbol("network.netmask"),
					context.efactory.numeral(i),
					context.efactory.symbol(name)
				),
				context.efactory.numeral(ipr.range.bitmask)
			))
		}
		return exprArr
	}
}
