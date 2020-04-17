from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller import dpset
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import *
from ryu.lib import hub
from ryu.topology import event
import networkx as nx
import time, json, sys, os

sys.path.append(os.getcwd())

class FF_test(app_manager.RyuApp):
    def __init__(self, *args, **kwargs):
        super(FF_test, self).__init__(*args, **kwargs)
        # self.monitor_thread = hub.spawn(self._monitor)

    def goto_table(self, datapath, priority, match, gototable, now_table=0, buffer_id=None):
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionGotoTable(table_id=gototable)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst, table_id=now_table)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id

        if dpid == 3:
            buckets = [
                parser.OFPBuckets(
                    actions = [parser.OFPAcionOutput(2)],
                    watch_port = 2
                ),
                parser.OFPBuckets(
                    actions = [parser.OFPAcionOutput(1)],
                    watch_port = 1
                )
            ]

            req = parser.OFPGroupMod(
                    datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_FF, 1, 
                    buckets
                )
            datapath.send_msg(req)

            buckets = buckets[::-1]
            req = parser.OFPGroupMod(
                    datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_FF, 2, 
                    buckets
                )
            datapath.send_msg(req)

            match = parser.OFPMatch(in_port = 1)
            actions = parser.OFPActionGroup(1)
            self.add_flow(datapath, 1, match, actions)

            match = parser.OFPMatch(in_port = 2)
            actions = parser.OFPActionGroup(2)
            self.add_flow(datapath, 1, match, actions)

        else:
            ip_range = ['10', '0', str(dpid), '0']
            ip_range = '.'.join(ip_range)
            ip_mask = '255.255.255.0'

            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_dst = (ip_range, ip_mask)
                )
            actions = parser.OFPAcionOutput(1)
            self.add_flow(datapath, 2, match, actions)

            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_ARP,
                arp_tpa = (ip_range, ip_mask)
                )
            actions = parser.OFPAcionOutput(1)
            self.add_flow(datapath, 2, match, actions)

            match = parser.OFPMatch(in_port = 1)
            actions = parser.OFPAcionOutput(3)
            self.add_flow(datapath, 1, match, actions)

            match = parser.OFPMatch(in_port = 3)
            actions = parser.OFPAcionOutput(2)
            self.add_flow(datapath, 1, match, actions)
            
    def add_flow(self, datapath, priority, match, actions, table_id = 0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst, table_id=table_id)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        arp_pkt = pkt.get_protocol(arp.arp)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
    
        if pkt.get_protocol(ipv6.ipv6):
            match = parser.OFPMatch(eth_type = eth.ethertype)
            actions = []
            self.add_flow(datapath, 1, match, actions)
            return None

        dst = eth.dst
        src = eth.src

        dpid = datapath.id

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)
