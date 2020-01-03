import time
import os
from mininet.net import Mininet
from mininet.node import RemoteController,OVSSwitch
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel

def topology(remoteip,ofversion):
	
	"***Create a network."
	net = Mininet(controller=RemoteController,switch=OVSSwitch)
	
	print("***Creating hosts")
	h1 = net.addHost("h1",mac="00:00:00:00:00:01",ip="10.0.0.1")
	h2 = net.addHost("h2",mac="00:00:00:00:00:02",ip="10.0.0.2")
	# h3 = net.addHost("h3",mac="00:00:00:00:00:03",ip="10.0.0.3")
	print("***Creating switches")
	s1 = net.addSwitch("s1",protocols=ofversion)
	# s2 = net.addSwitch("s2",protocols=ofversion)
	c1 = net.addController("c1",controller=RemoteController,ip=remoteip,port=6653)

	print("***Create links")
	#switchLinkOpts = dict(bw=10,delay="1ms")
	#hostLinksOpts = dict(bw=100)
	
	net.addLink(s1, h1, 1)
	net.addLink(s1, h2, 2)
	# net.addLink(s1, s2, 3, 1)
	print("***Building network.")
	net.build()
	s1.start([c1])
	# s2.start([c1])
	
	print("***Starting network")
	c1.start()
	CLI(net)
	
	print("***Stoping network")
	net.stop()
	
if __name__ == "__main__":
	setLogLevel("info")
	topology("127.0.0.1","OpenFlow13")