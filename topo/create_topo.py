from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
import json
import sys
sys.path.append("..")
# from SFlow.enable_sflow import EnableSFlow
from Flow.base_net import BaseNet



def topology(remoteip, ofversion, file = 'config/2pod_topo.json'):
    net = BaseNet(controller=RemoteController,switch=OVSSwitch)
    c1 = net.addController("c1",controller=RemoteController,ip=remoteip,port=6653)
    switch_dict = {}
    switch_list = []
    switch_port = {}
    with open(file, 'r') as load_f:
        load_dict = json.load(load_f)
    for pod in load_dict['pod_list']:
        sw = net.addSwitch(pod['name'], protocols=ofversion)
        switch_list.append(sw)
        switch_dict[pod['name']] = sw
        switch_port[pod['name']] = 0
        for host in pod['host_list']:
            h = net.addHost(host['name'], ip=host['ip'])
            switch_port[pod['name']] += 1
            net.addLink(switch_dict[pod['name']], h, switch_port[pod['name']])
    for link in load_dict['link_graph']:
        switch_port[link['begin']] += 1
        switch_port[link['end']] += 1
        print link
        net.addLink(switch_dict[link['begin']], switch_dict[link['end']], switch_port[link['begin']], switch_port[link['end']])
    
    print("***Building network.")
    net.build()
    for sw in switch_list:
        sw.start([c1])
    
    print("***Starting network")
    c1.start()
     
    # EnableSFlow(net, sampling_rate=10, polling_rate=10)
    # do something

    simple_CLI(net)

    #
    # CLI(net)
    print("***Stoping network")
    net.stop()

def simple_CLI(net):
    while(True):
        x = raw_input()
        if x == 'exit':
            break
        if x == 'elephant':
            net.mouse_elephant_flow()
        elif x== 'traffic':
            # read traffic
            # param: traffic_arr time_arr

            traffic_arr = [[[1000 for i in range(8)] for j in range(8)]]
            time_arr = [10]
            net.simulate_traffic(traffic_arr, time_arr)
        elif x == 'cli':
            CLI(net)

if __name__ == "__main__":
    setLogLevel("debug")
    topology("127.0.0.1","OpenFlow13")
    
