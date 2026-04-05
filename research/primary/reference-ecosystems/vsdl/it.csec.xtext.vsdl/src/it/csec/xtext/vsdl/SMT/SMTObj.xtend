package it.csec.xtext.vsdl.SMT

import org.smtlib.IExpr.IFcnExpr

import java.util.ArrayList

abstract class SMTObj<T> {
	def public static getIAssertions(String name, SMTContext context) {}
	
	def public ArrayList<IFcnExpr> compile(T obj, String name, SMTContext context);
}