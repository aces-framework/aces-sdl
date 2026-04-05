package it.csec.xtext.vsdl.SMT

import org.eclipse.emf.ecore.EObject
import java.lang.reflect.Method
import org.smtlib.IExpr.IFcnExpr
import java.util.ArrayList

class SMTObjFactory {
	EObject obj
	
	new(EObject obj) {
		this.obj = obj
	}
	
	def private getSimpleName() {
		// remove Impl
		return obj.getClass.getSimpleName.substring(
			0,
			obj.class.getSimpleName.length - 4
		)
	}	
   
	def private getName() {
		// remove package
		return obj.class.package.toString.substring(
			8,
			obj.class.package.toString.length - 4
		) + this.getSimpleName()
	}	
	
	def private getSMTName() {
		return this.class.package.toString.substring(8) + ".SMT" + this.getSimpleName()
	}
	
	def ArrayList<IFcnExpr> compile(String name, SMTContext context) {
		var cls = this.^class.classLoader.loadClass(this.getSMTName())

		var newobj = cls.newInstance;
		
		// context.console.stream.println("compiling: " + name + ": " + cls.name)
		var imethod = cls.getMethod("getIAssertions", String, Class.forName("it.csec.xtext.vsdl.SMT.SMTContext"))
		imethod.invoke(newobj, name, context)
	
		var Method method
		try {
			method = cls.getMethod("compile", Class.forName(this.getName()), String, Class.forName("it.csec.xtext.vsdl.SMT.SMTContext"));
		 } catch (NoSuchMethodException e) {
			try {
				method = cls.getMethod("compile", Class.forName("java.lang.Object"), String, Class.forName("it.csec.xtext.vsdl.SMT.SMTContext"));
			 }  catch (Exception ex) {
			 	
				for (Method m : cls.methods) {
					context.console.stream.println(this.getSMTName() + ": " + m.toString)
				}
				//return newArrayOfSize(1)
			}
		}
		return method.invoke(newobj, obj, name, context) as ArrayList<IFcnExpr>	
	}
}