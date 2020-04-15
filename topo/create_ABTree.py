from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import sys, os
from ABTree import ABTree
from collections import defaultdict
import json

def create_topo(k = 4, L = 3, ofversion = "OpenFlow13", remoteip = "127.0.0.1"):
    tree = ABTree(k, L).tree
    net = Mininet(controller=RemoteController, switch=OVSSwitch)
    c1 = net.addController("c1", controller=RemoteController, ip=remoteip, port=6653)
    sw_list = [[] for i in range(L)]
    host_list = []
    sw_dict = {}

    for node in tree.nodes.data():
        print(node)
        if node[0][0] == 's':
            dpid = node[0][1:]
            sw_dict[dpid] = node[1]['layer']
            sw_list[node[1]['layer'] - 1].append(node[0])
        else:
            host_list.append((node[0], node[1]['ip']))

    with open("./topo/switch_dict.json", 'w') as f:
        json.dump(sw_dict, f)

    info("*** Add Switch\n")
    for i in range(L):
        for sw in sw_list[L - i - 1]:
            net.addSwitch(sw, protocols = ofversion)
    
    info("*** Add Host\n")
    for (host, ip) in host_list:
        net.addHost(host, ip = ip)
    
    info("*** Add Links\n")
    for edge in list(tree.edges):
        net.addLink(edge[0], edge[1], tree.edges[edge]['port1'], tree.edges[edge]['port2'])
    
    info( '*** Starting network\n')
    net.build()
    
    info( '*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info( '*** Starting switches\n')
    for i in range(L):
        for sw in sw_list[L - i - 1]:
            net.get(sw).start([c1])

    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel( 'info' )
    # Use default parameters
    create_topo()               