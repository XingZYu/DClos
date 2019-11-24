# Copyright (C) 2016 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from ryu.base import app_manager
from operator import attrgetter

from ryu.app import simple_switch_13
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import *
from ryu.lib.packet import ether_types
from ryu.lib import hub
from config.read import *


class SimpleMonitor13(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.net_info = read_topo('../config/topo.json')
        print(self.net_info)
        # self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    def add_flow(self, datapath, priority, match, actions, table_id=0, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst, table_id=table_id)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst, table_id=table_id)
        datapath.send_msg(mod)

    # def delete_flow(self, datapath, match, table_id=0):
    #     ofproto = datapath.ofproto
    #     parser = datapath.ofproto_parser
    #     mod = parser.OFPFlowMod(datapath=datapath, match=match, command=ofproto.OFPFC_DELETE, table_id=table_id)
    #     datapath.send_msg(mod)

    def goto_table(self, datapath, priority, match, gototable, now_table=0, buffer_id=None):
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionGotoTable(table_id=gototable)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst, table_id=now_table)
        datapath.send_msg(mod)

    # def goto_group(self, datapath, priority, match, group_id, table_id, buffer_id=None):
    #     return 1



    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id
        switch_info = self.net_info[dpid]

        # match flow to the switch host, goto table 1
        kwargs = dict(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=(switch_info['ip'][0],switch_info['ip'][1]))
        match = parser.OFPMatch(**kwargs)
        self.goto_table(datapath, 4, match, gototable=1)

        kwargs = dict(eth_type=ether_types.ETH_TYPE_ARP, arp_tpa=(switch_info['ip'][0],switch_info['ip'][1]))
        match = parser.OFPMatch(**kwargs)
        self.goto_table(datapath, 4, match, gototable=1)

        # table 1: go to which host
        for host_ip in switch_info['host']:
            actions = [parser.OFPActionOutput(switch_info['host'][host_ip])]

            kwargs = dict(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=host_ip)
            match = parser.OFPMatch(**kwargs)
            self.add_flow(datapath, 1, match, actions, table_id=1)

            kwargs = dict(eth_type=ether_types.ETH_TYPE_ARP, arp_tpa=host_ip)
            match = parser.OFPMatch(**kwargs)
            self.add_flow(datapath, 1, match, actions, table_id=1)




        # match flow from the switch host
        kwargs = dict(eth_type=ether_types.ETH_TYPE_IP, ipv4_src=(switch_info['ip'][0],switch_info['ip'][1]))
        match = parser.OFPMatch(**kwargs)
        self.goto_table(datapath, 3, match, gototable=2)

        kwargs = dict(eth_type=ether_types.ETH_TYPE_ARP, arp_spa=(switch_info['ip'][0],switch_info['ip'][1]))
        match = parser.OFPMatch(**kwargs)
        self.goto_table(datapath, 3, match, gototable=2)



        # group table

        for i in range(1,len(self.net_info)):
            if i == dpid:
                continue
            group_id = i
            watch_port = ofproto_v1_3.OFPP_ANY
            watch_group = ofproto_v1_3.OFPQ_ALL
            buckets = []
            for switch_id in switch_info['switch']:
                weight = 1
                # if direct send, increase weight
                if switch_id == i:
                    weight = 2
                port = switch_info['switch'][switch_id]
                actions = [parser.OFPActionOutput(port)]
                buckets.append(parser.OFPBucket(weight, watch_port, watch_group, actions))
            req = parser.OFPGroupMod(datapath, ofproto.OFPFC_ADD,ofproto.OFPGT_SELECT, group_id, buckets)
            datapath.send_msg(req)

        # go to which switch
        for switch_id in switch_info['switch']:

            port = switch_info['switch'][switch_id]
            target_swtich = self.net_info[switch_id]
            target_ip = target_swtich['ip']
            print '----------------------'
            print target_swtich, target_swtich['id']

            # table 2: match which switch dst is, multipath by group table

            actions = [parser.OFPActionGroup(group_id=target_swtich['id'])]
            # actions = [parser.OFPActionOutput(port)]
            kwargs = dict(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=(target_ip[0], target_ip[1]))
            match_1 = parser.OFPMatch(**kwargs)
            # go to group
            self.add_flow(datapath, 1, match_1, actions, table_id=2)

            kwargs = dict(eth_type=ether_types.ETH_TYPE_ARP, arp_tpa=(target_ip[0], target_ip[1]))
            match_2 = parser.OFPMatch(**kwargs)
            self.add_flow(datapath, 1, match_2, actions, table_id=2)


            # table 3: transmit to dst switch
            actions = [parser.OFPActionOutput(port)]

            self.add_flow(datapath, 1, match_1, actions, table_id=3)
            self.add_flow(datapath, 1, match_2, actions, table_id=3)



        
            

        

        # no match in table 0, goto table 3
        # match = parser.OFPMatch() 
        # actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        # self.goto_table(datapath, 0, match, gototable=3, now_table=0)

        # no match in table 3, packetin
        self.add_flow(datapath, 0, match, actions, table_id=3)
                                        
        




    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        pkt = packet.Packet(msg.data)
        # eth = pkt.get_protocols(ethernet.ethernet)
        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
        pkt_icmp = pkt.get_protocol(icmp.icmp)
        pkt_arp = pkt.get_protocol(arp.arp)
        print('icmp',pkt_icmp)
        print('pkt_ipv4', pkt_ipv4)
        print('arp', pkt_arp)
        # in_port = msg.match['in_port']
        # ipv4_src = eth.src
        # ipv4_dst = eth.dst
        # self.logger.info('packet in !!! %s %s %s', in_port, ipv4_src, ipv4_dst)
        # print(msg.match)

