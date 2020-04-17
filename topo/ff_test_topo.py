from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import sys, os
from collections import defaultdict
import json

def create_topo(ofversion = "OpenFlow13", remoteip = "127.0.0.1"):
    net = Mininet(controller=RemoteController, switch=OVSSwitch)
    c1 = net.addController("c1", controller=RemoteController, ip=remoteip, port=6653)

    info("*** Add Switch\n")
    net.addSwitch('s1', protocols = ofversion)
    net.addSwitch('s2', protocols = ofversion)
    net.addSwitch('s3', protocols = ofversion)
    
    info("*** Add Host\n")
    net.addHost("s1h1", ip = "10.0.1.1")
    net.addHost("s2h1", ip = "10.0.2.1")
    
    info("*** Add Links\n")
    net.addLink('s1', 's2', 2, 2)
    net.addLink('s1', 's3', 3, 1)
    net.addLink('s2', 's3', 3, 2)
    net.addLink('s1', 's1h1', 1)
    net.addLink('s2', 's2h1', 1)
    
    info( '*** Starting network\n')
    net.build()
    
    info( '*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info( '*** Starting switches\n')
    net.get("s1").start([c1])
    net.get("s2").start([c1])
    net.get("s3").start([c1])

    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel( 'info' )
    # Use default parameters
    create_topo()               
