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
print(sys.path)
from topo.ABTree import ABTree

K = 4
L = 3

class F10Switch(app_manager.RyuApp):
    def __init__(self, *args, **kwargs):
        super(F10Switch, self).__init__(*args, **kwargs)
        self.network = ABTree(K, L).ryu_tree
        self.hosts = {}
        for node in self.network.nodes:
            if self.network.nodes[node]['layer'] == 0:
                dpid = list(self.network.adj[node])[0]
                self.hosts[dpid] = node
        # self.monitor_thread = hub.spawn(self._monitor)
    
    def _monitor(self):
        while True:
            self._show()
            hub.sleep(10)

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

        # self.logger.info(datapath.id)

        layer = self.network.nodes[datapath.id]['layer']

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.  The bug has been fixed in OVS v2.1.0.
        n = K // 2

        match = parser.OFPMatch()
        self.goto_table(datapath, 0, match, 1)

        match = parser.OFPMatch(eth_type = 0x86DD)
        actions = []
        self.add_flow(datapath, 1, match, actions)

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions, table_id = 1)

        actions = [parser.OFPActionOutput(ofproto.OFPP_IN_PORT,
                  ofproto.OFPCML_NO_BUFFER)]
        buckets = [parser.OFPBucket(actions = actions)]
        req = parser.OFPGroupMod(
                datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_INDIRECT, 100, 
                buckets
            )
        datapath.send_msg(req)

        # For switches 1 to n are downlink ports
        # n+1 to K are uplink ports
        if layer == 1:
            # Action group 1: 
            # Received from hosts, send to uplinks
            buckets = []
            for i in range(n + 1, K + 1):
                bucket_action = [parser.OFPActionOutput(i)]
                buckets.append(parser.OFPBucket(
                            weight=1,
                            actions=bucket_action
                        ))
            req = parser.OFPGroupMod(
                    datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_SELECT, 1,
                    buckets
                )
            datapath.send_msg(req)

            match = parser.OFPMatch(in_port = 1)
            actions = [parser.OFPActionGroup(1)]
            self.add_flow(datapath, 1, match, actions)

            # Received from L2 switches, send to hosts
            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_dst = self.hosts[datapath.id]
                )
            actions = [parser.OFPActionOutput(1)]
            self.add_flow(datapath, 2, match, actions)

            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_ARP,
                arp_tpa = self.hosts[datapath.id]
                )
            actions = [parser.OFPActionOutput(1)]
            self.add_flow(datapath, 2, match, actions)
            
            # Received from L2 switches, send to backup path
            for i in range(1, n+1):
                match = parser.OFPMatch(in_port = i + n)
                out_port = i % n + 1 + n
                actions = [parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)

        if layer == 2:
            # Table 0
            # Check if it's the target pod
            # If this is the target pod, send to L1 switches
            # Else go to table 1 (Table miss entry in table 0)
            for dpid in self.network.adj[datapath.id]:
                if int(self.network.nodes[dpid]['layer']) == 1:
                    out_port = min(
                        self.network[datapath.id][dpid]['port1'],
                        self.network[datapath.id][dpid]['port2']
                        )

                    buckets = [parser.OFPBucket(
                        actions = [parser.OFPActionOutput(out_port)],
                        watch_port = out_port
                        )]
                    for i in range(1, n):
                        port = (out_port + i) % (K + 1)
                        buckets.append(parser.OFPBucket(
                            actions = [parser.OFPActionOutput(port)],
                            watch_port = port
                            ))
                    req = parser.OFPGroupMod(
                            datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_FF, out_port,
                            buckets
                        )
                    datapath.send_msg(req)
                     
                    match = parser.OFPMatch(
                        eth_type=ether_types.ETH_TYPE_IP,
                        ipv4_dst = (self.network.nodes[dpid]['ip_range'], 
                                    self.network.nodes[dpid]['ip_mask']),
                        )
                    actions = [parser.OFPActionGroup(out_port)]
                    self.add_flow(datapath, 1, match, actions)

                    match = parser.OFPMatch(
                        eth_type=ether_types.ETH_TYPE_ARP,
                        arp_tpa = (self.network.nodes[dpid]['ip_range'], 
                                    self.network.nodes[dpid]['ip_mask']),
                        )
                    actions = [parser.OFPActionGroup(out_port)]
                    self.add_flow(datapath, 2, match, actions)
            
            # Table 1
            # If received from downlinks, send packet to Layer 3 switches 
            # Common Situation: receive packet from L1 switches
            # Randomly distribute flows to uplinks
            # If one uplink fail, go to the other
            for i in range(n + 1, K + 1):
                buckets = [parser.OFPBucket(
                            actions = [parser.OFPActionOutput(i)],
                            watch_port = i
                        )]
                
                for j in range(1, n + 1):
                    out_port = (i + j) % (K + 1) + n + 1
                    buckets.append(
                        parser.OFPBucket(
                            actions = [parser.OFPActionOutput(out_port)],
                            watch_port = out_port
                        )
                    )
                
                req = parser.OFPGroupMod(
                    datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_FF, i, 
                    buckets
                )
                datapath.send_msg(req)

            buckets = []
            for i in range(n + 1, K + 1):
                bucket_action = [parser.OFPActionGroup(i)]
                buckets.append(parser.OFPBucket(
                    weight = 1,
                    actions = bucket_action
                ))
            req = parser.OFPGroupMod(
                datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_SELECT, 0, 
                buckets
            )
            datapath.send_msg(req)

            for i in range(1, n + 1):
                match = parser.OFPMatch(in_port = i)
                actions = [parser.OFPActionGroup(0)]
                self.add_flow(datapath, 1, match, actions, table_id = 1)

            # Receive packets from L3 switches
            # If received from uplinks, meaning a failure in a L3-L2 link
            # Send to next uplink
            for i in range(1, n + 1):
                match = parser.OFPMatch(in_port = i + n)
                actions = [parser.OFPActionOutput((i + n) % K  + n + 1)]
                self.add_flow(datapath, 1, match, actions, table_id = 1)

        if layer == 3:
            # If no failure, send to the other link
            # If one link failed, send back
            for in_port in range(1, n + 1):
                buckets = []
                for i in range(0, n):
                    out_port = (in_port + i) % n + 1
                    if out_port == in_port:
                        buckets.append(parser.OFPBucket(
                            actions = [parser.OFPActionGroup(100)],
                            watch_group = 100
                            ))
                    else:
                        buckets.append(parser.OFPBucket(
                            actions = [parser.OFPActionOutput(out_port)],
                            watch_port = out_port
                        ))
                req = parser.OFPGroupMod(
                    datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_FF, in_port, 
                    buckets
                )
                datapath.send_msg(req)

            for in_port in range(1, n + 1):
                match = parser.OFPMatch(in_port = in_port)
                actions = [parser.OFPActionGroup(in_port)]
                
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
