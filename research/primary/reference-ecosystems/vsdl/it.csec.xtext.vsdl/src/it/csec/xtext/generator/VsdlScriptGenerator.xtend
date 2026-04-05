package it.csec.xtext.generator

import org.eclipse.core.commands.AbstractHandler;
import org.eclipse.core.commands.ExecutionEvent;
import org.eclipse.core.commands.ExecutionException;
// import org.eclipse.ui.IWorkbenchWindow;
import org.eclipse.ui.handlers.HandlerUtil;
//import org.eclipse.jface.dialogs.MessageDialog;
import org.eclipse.core.resources.IFile
import org.eclipse.jface.viewers.IStructuredSelection
import java.io.FileReader
import java.io.BufferedReader
import it.csec.xtext.vsdl.Terraform.Scenario
/* import it.csec.xtext.vsdl.Terraform.Node
import org.eclipse.core.resources.ResourcesPlugin
import org.eclipse.core.resources.IFolder
import org.eclipse.core.runtime.Path
import java.io.File */
import it.csec.xtext.VsdlResources

public class VsdlScriptGenerator extends AbstractHandler {
	def override public Object execute(ExecutionEvent event) throws ExecutionException {
		//var console = new VsdlConsole("terraform")
		//var window = HandlerUtil.getActiveWorkbenchWindowChecked(event)
		//MessageDialog.openInformation(window.getShell(), "Test", "Hello, Eclipse world");

		var activeSelection = HandlerUtil.getActiveMenuSelection(event) as IStructuredSelection 

		if (activeSelection.firstElement instanceof IFile) {
			var file = activeSelection.firstElement as IFile;
			var fr = new FileReader(file.location.toString)
			var br = new BufferedReader(fr)

			var scenario = new Scenario(file.name.substring(0, file.name.indexOf("_")))
			var String line
			
			scenario.console.stream.println("Generating Terraform scripts for scenario " + scenario.name)
			while ((line = br.readLine) !== null) {
				scenario.setElementFromValue(line)								
			}
			br.close
						
			scenario.console.stream.println("ttu: " + scenario.ttu)
			var ttuStep = Integer.parseInt(VsdlResources.getTtuStep)
			
			for (var i = 0; i <= scenario.ttu; i += ttuStep) {
				scenario.createResource("provider.tf", i, scenario.doTerraformProvider.toString)
				scenario.createResource("network_bogus.tf", i, scenario.doTerraformBogusNet.toString)

				for (String netName : scenario.networks.keySet) {
					var net = scenario.networks.get(netName).get(i)
					scenario.createResource("network_" + netName + ".tf", i, net.toTerraformString().toString)
					scenario.createResource("router_" + netName + ".tf", i, net.router.toTerraformString().toString)
				}

				for (String nodeName : scenario.nodes.keySet) {
					var node = scenario.nodes.get(nodeName).get(i)
					scenario.createResource(
						"node_" + nodeName + ".tf",
						i,
						node.toTerraformString().toString
					)
				}
			}
			scenario.console.stream.println("Done.")
		}
		return null;
	}
}