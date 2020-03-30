from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch, UserSwitch
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
import json
import sys
sys.path.append("..")
from SFlow.enable_sflow import EnableSFlow
from Flow.base_net import BaseNet
import re

def unicode_convert(ori_dict):
    if isinstance(ori_dict, dict):
        return {unicode_convert(key): unicode_convert(value) for key, value in ori_dict.iteritems()}
    elif isinstance(ori_dict, list):
        return [unicode_convert(element) for element in ori_dict]
    elif isinstance(ori_dict, unicode):
        return ori_dict.encode('utf-8')
    else:
        return ori_dict


def topology(remoteip, ofversion, file = '../config/8pod_topo.json'):
    net = BaseNet(
        controller=RemoteController,
        switch=UserSwitch,
        # autoSetMacs=True,
        autoStaticArp=True,
    )
    c1 = net.addController("c1",controller=RemoteController,ip=remoteip,port=6653)
    switch_dict = {}
    switch_list = []

    with open(file, 'r') as load_f:
        load_dict = json.load(load_f)
    load_dict = unicode_convert(load_dict)

    for pod in load_dict['pod_list']:
        sw = net.addSwitch(pod['name'], protocols=ofversion)
        switch_list.append(sw)
        switch_dict[pod['name']] = sw
        # obtain switch name number, eg: s1->1
        switch_num = int(re.findall(r'\d+', pod['name'])[0])
        
        for host in pod['host_list']:
            h = net.addHost(host['name'], ip=host['ip'], mac=host['mac'])
            net.addLink(sw, h, switch_num, bw=1000)
     
    for link in load_dict['link_graph']:
        switch_begin_num = int(re.findall(r'\d+', link['begin'])[0])
        switch_end_num = int(re.findall(r'\d+', link['end'])[0])
        net.addLink(switch_dict[link['begin']], switch_dict[link['end']], switch_end_num, switch_begin_num, bw=1000)

    print("***Building network.")
    net.build()
    for sw in switch_list:
        sw.start([c1])
    
    print("***Starting network")
    c1.start()
     
    # EnableSFlow(net, sampling_rate=10, polling_rate=10)
    # net.mouse_elephant_flow()
    CLI(net)

    print("***Stoping network")
    net.stop()

if __name__ == "__main__":
    setLogLevel("info")
    topology("127.0.0.1","OpenFlow13")
    
