package it.csec.xtext

import java.net.URL
import java.util.Properties
import org.openstack4j.openstack.OSFactory
import org.openstack4j.model.compute.Flavor
import java.util.List
import java.util.ArrayList
import javax.xml.parsers.DocumentBuilderFactory

import org.w3c.dom.Node;
import org.w3c.dom.Element;
import java.util.Set
import java.util.HashSet

class VsdlResources {
	private static def getResourceInputStream() {
		var url = new URL("platform:/plugin/it.csec.xtext.vsdl/resources.xml");
		return url.openConnection().getInputStream();
	}
	
	static def getOssFamilyIds(String family) {
		var List<Integer> res = new ArrayList<Integer>()

		var inputStream = getResourceInputStream

		var dbFactory = DocumentBuilderFactory.newInstance;
		var dBuilder = dbFactory.newDocumentBuilder();
		var doc = dBuilder.parse(inputStream);

		var nList = doc.getElementsByTagName("os")
		for (var i = 0; i < nList.getLength(); i++) {
			var Node nNode = nList.item(i);

			if (nNode.getNodeType() == Node.ELEMENT_NODE) {
				var Element eElement = nNode as Element;
				
				if (eElement.getElementsByTagName("family").item(0).getTextContent().equals(family)) {
					res.add(Integer.parseInt(eElement.getAttribute("id")))
				}
			}
		}

		inputStream.close
		return res
	}
	
	static def getOsId(String name) {
		var inputStream = getResourceInputStream

		var dbFactory = DocumentBuilderFactory.newInstance;
		var dBuilder = dbFactory.newDocumentBuilder();
		var doc = dBuilder.parse(inputStream);

		var nList = doc.getElementsByTagName("os")
		var i = 0
		while (i < nList.getLength()) {
			var Node nNode = nList.item(i);

			if (nNode.getNodeType() == Node.ELEMENT_NODE) {
				var Element eElement = nNode as Element;

				if (eElement.getElementsByTagName("name").item(0).getTextContent().equals(name)) {
					inputStream.close
					return Integer.parseInt(eElement.getAttribute("id"))
				}
			}

			i++
		}

		inputStream.close
		return i
	}
	
	static def getOsImage(int id) {
		var inputStream = getResourceInputStream

		var dbFactory = DocumentBuilderFactory.newInstance;
		var dBuilder = dbFactory.newDocumentBuilder();
		var doc = dBuilder.parse(inputStream);

		var nList = doc.getElementsByTagName("os")
		var i = 0
		while (i < nList.getLength()) {
			var Node nNode = nList.item(i);

			if (nNode.getNodeType() == Node.ELEMENT_NODE) {
				var Element eElement = nNode as Element;

				if (Integer.parseInt(eElement.getAttribute("id")) == id) {
					inputStream.close
					return eElement.getElementsByTagName("image").item(0).getTextContent()
				}
			}

			i++
		}

		inputStream.close
		return ""
	}
			
	static def getOssName() {
		var List<String> res = new ArrayList<String>()
		
		var inputStream = getResourceInputStream

		var dbFactory = DocumentBuilderFactory.newInstance;
		var dBuilder = dbFactory.newDocumentBuilder();
		var doc = dBuilder.parse(inputStream);

		var nList = doc.getElementsByTagName("os")
		for (var i = 0; i < nList.getLength(); i++) {
			var Node nNode = nList.item(i);

			if (nNode.getNodeType() == Node.ELEMENT_NODE) {
				var Element eElement = nNode as Element;
				res.add(eElement.getElementsByTagName("name").item(0).getTextContent())
			}
		}

		inputStream.close
		return res
	}
		
	static def getOssFamily() {
		var List<String> res = new ArrayList<String>()
		var Set<String> hs = new HashSet<String>();
		
		var inputStream = getResourceInputStream

		var dbFactory = DocumentBuilderFactory.newInstance;
		var dBuilder = dbFactory.newDocumentBuilder();
		var doc = dBuilder.parse(inputStream);

		var nList = doc.getElementsByTagName("os")
		for (var i = 0; i < nList.getLength(); i++) {
			var Node nNode = nList.item(i);

			if (nNode.getNodeType() == Node.ELEMENT_NODE) {
				var Element eElement = nNode as Element;
				res.add(eElement.getElementsByTagName("family").item(0).getTextContent())
				// env.console.stream.print("Curr: " + eElement.getAttribute("id"));
			}
		}

		inputStream.close
		hs.addAll(res);
		res.clear();
		res.addAll(hs);
		
		return res	
	}
	
	private static def getConfig() {
		var url = new URL("platform:/plugin/it.csec.xtext.vsdl/config.properties");
		
 		var input = url.openConnection().getInputStream()
		var prop = new Properties()
		prop.load(input)
		input.close
		
		return prop
	}
	
	def static getOSuser() {
		return getConfig.getProperty("openstack_user")
	}
	
	def static getOSpassword() {
		return getConfig.getProperty("openstack_password")		
	}

	def static getOSurl() {
		return getConfig.getProperty("openstack_url")		
	}

	def static getOStenant() {
		return getConfig.getProperty("openstack_tenant_name")		
	}

	def static getSolver() {		
		return getConfig.getProperty("solver")
	}

	def static getTtu() {		
		return getConfig.getProperty("ttu")
	}

	def static getTtuStep() {		
		return getConfig.getProperty("ttustep")
	}
	
	def static getOSClient() {
		var prop = getConfig
		
		return OSFactory.builderV2().endpoint(prop.getProperty("openstack_url")).credentials(
			prop.getProperty("openstack_user"), prop.getProperty("openstack_password")).tenantName(
			prop.getProperty("openstack_user")).authenticate()
	}

	def static getFlavors() {		
		return getOSClient.compute.flavors().list()
	}
	
	def static getFlavor(String name) {		
		var fs = getFlavors
		
		var i = 0		
		while (i < fs.size) {
			if (fs.get(i).name.equals(name)) {
				return fs.get(i)
			}
			i++			
		}

		return null
	}
	
	def static getFlavorsName() {
		var List<String> res = new ArrayList<String>()
					
		for (Flavor f : getOSClient.compute.flavors().list()) {
			 res.add(f.name)
		}				
		
		return res
	}
}