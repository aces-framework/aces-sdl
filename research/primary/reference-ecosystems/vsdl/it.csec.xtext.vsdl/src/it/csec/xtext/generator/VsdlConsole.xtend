package it.csec.xtext.generator

import org.eclipse.ui.console.MessageConsoleStream
import org.eclipse.ui.console.ConsolePlugin
import org.eclipse.ui.console.IConsoleManager
import org.eclipse.ui.console.IConsole
import org.eclipse.ui.console.MessageConsole

class VsdlConsole {
	private MessageConsoleStream stream

	new(String name) {
		stream = findConsole(name).newMessageStream
	}
	
	def private MessageConsole findConsole(String name) {
		val ConsolePlugin cplugin = ConsolePlugin.getDefault();
		val IConsoleManager conMan = cplugin.getConsoleManager();
		val existing = conMan.getConsoles();
		for (var i = 0; i < existing.length; i++) {
			if (name.equals(existing.get(i).getName())) {
				return existing.get(i) as MessageConsole;
			}
		}
		// no console found
		val console = new MessageConsole(name, null);
		conMan.addConsoles(#[console] as IConsole[])

		return console
	}	
	
	def getStream() {
		return stream
	}
}