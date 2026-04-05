package it.csec.xtext.vsdl.Terraform

import org.eclipse.xtend.lib.annotations.Accessors
import it.csec.xtext.VsdlResources
import java.util.ArrayList

class Node extends ScenElem {
	@Accessors
	private var Flavor flavor
	@Accessors
	private String flavorId
	@Accessors
	private int OS
	@Accessors
	private String OSid
	@Accessors
	private var ArrayList<Interface> interfaces
	
	new(String name) {
		this.name = name
		
		flavor = new Flavor()
		OS = 0
		OSid = ""
		
		interfaces = new ArrayList<Interface>
	}
	
	def toTerraformString() {
		var flag = false
		var i = 0
		var cf = VsdlResources.OSClient.compute
		var fl = cf.flavors.list
		
		// search for existing flavor in OpenStack (TODO: check for correct um)
		// http://docs.openstack.org/admin-guide/compute-flavors.html
		while (! flag && i < fl.size) {
			var f = fl.get(i)
			if (f.disk == (flavor.disk / 1024) && 
				f.ram == flavor.ram &&	
				f.vcpus == flavor.vcpu) {
					flag = true
					flavorId = f.id
				}
			i++
		}
		
		if (! flag) {
			// we can't find a correct flavor..yup! create it
			var fname = scenario + "_" + name + "_" + ttuStep
			
			// delete flavour with same name
			i = 0
			while (! flag && i < fl.size) {
				if (fl.get(i).name == fname) {
					cf.flavors.delete(fl.get(i).id)
					flag = true	
				}
				i++
			}
			
			var nf = cf.flavors.create(fname, flavor.ram, flavor.vcpu, flavor.disk / 1024, 0, 0, 1.0f, true)
			flavorId = nf.id
		}
		
		var OSname = VsdlResources.getOsImage(OS)
		var il = cf.images.list
		
		i = 0
		flag = false
		while (! flag && i < il.size) {
			if (il.get(i).name == OSname) {
				OSid = il.get(i).id
				flag = true		
			}
			i++
		}
		
		if (OSid == "") {
			throw new Exception("Invalid OS for node " + name)
		}

		'''
		resource "openstack_compute_instance_v2" "«name»" {
		  name = "«name»"
		  image_id = "«OSid»"
		  flavor_id = "«flavorId»"
		  
		  # admin_pass = "Enrico"
		  «IF interfaces !== null»
		   «FOR  n : interfaces»
		   network {
		      uuid = "${openstack_networking_network_v2.«n.networkid».id}"
		      «IF n.address !== ""»
		      fixed_ip_v4 = "«n.address»"
		      «ENDIF»
		   }
		   «ENDFOR»
		  «ENDIF»
		  «IF interfaces !== null && interfaces.empty»
		  network {
		  	uuid = "${openstack_networking_network_v2.bogus.id}"
		  }
		  «ENDIF»
		}
		'''		
	}
}