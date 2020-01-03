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


class SimpleMonitor13(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        self.datapaths = {}
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

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(10)

    

    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)
    

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.  The bug has been fixed in OVS v2.1.0.
        # match = parser.OFPMatch(in_port=1,ipv4_src='192.168.1.1')

        # kwargs = dict(eth_type=ether_types.ETH_TYPE_IP,
        #       ipv4_src='10.0.0.1')
        # match = parser.OFPMatch(in_port=2)

        # actions = [parser.OFPActionOutput(1)]
        # self.add_flow(datapath, 2, match, actions)
        actions_1 = [parser.OFPActionOutput(2)]

        actions_2 = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]

        weight_1 = 50
        weight_2 = 5
        watch_port = ofproto_v1_3.OFPP_ANY
        watch_group = ofproto_v1_3.OFPQ_ALL
        buckets = [
            parser.OFPBucket(weight_1, watch_port, watch_group, actions_1),
            parser.OFPBucket(weight_2, watch_port, watch_group, actions_2)]

        group_id = 50
        req = parser.OFPGroupMod(datapath, ofproto.OFPFC_ADD,
                                     ofproto.OFPGT_SELECT, group_id, buckets)

        datapath.send_msg(req)





        kwargs = dict(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst='10.0.0.2')
        match = parser.OFPMatch(**kwargs)

        actions = [parser.OFPActionGroup(50)]
        self.add_flow(datapath, 3, match, actions)

        kwargs = dict(eth_type=ether_types.ETH_TYPE_ARP, arp_tpa='10.0.0.2')
        match = parser.OFPMatch(**kwargs)

        actions = [parser.OFPActionGroup(50)]
        self.add_flow(datapath, 3, match, actions)

        kwargs = dict(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst='10.0.0.1')
        match = parser.OFPMatch(**kwargs)

        actions = [parser.OFPActionOutput(1)]
        self.add_flow(datapath, 3, match, actions)

        kwargs = dict(eth_type=ether_types.ETH_TYPE_ARP, arp_tpa='10.0.0.1')
        match = parser.OFPMatch(**kwargs)

        actions = [parser.OFPActionOutput(1)]
        self.add_flow(datapath, 3, match, actions)



        # match = parser.OFPMatch()
        # actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
        #                                   ofproto.OFPCML_NO_BUFFER)]
        # self.add_flow(datapath, 0, match, actions)




    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        body = ev.msg.body

        self.logger.info('datapath         '
                         'in-port  eth-dst           '
                         'out-port packets  bytes')
        self.logger.info('---------------- '
                         '-------- ----------------- '
                         '-------- -------- --------')
        for stat in sorted([flow for flow in body if flow.priority == 1],
                           key=lambda flow: (flow.match['in_port'],
                                             flow.match['eth_dst'])):
            self.logger.info('%016x %8x %17s %8x %8d %8d',
                             ev.msg.datapath.id,
                             stat.match['in_port'], stat.match['eth_dst'],
                             stat.instructions[0].actions[0].port,
                             stat.packet_count, stat.byte_count)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body

        self.logger.info('datapath         port     '
                         'rx-pkts  rx-bytes rx-error '
                         'tx-pkts  tx-bytes tx-error')
        self.logger.info('---------------- -------- '
                         '-------- -------- -------- '
                         '-------- -------- --------')
        for stat in sorted(body, key=attrgetter('port_no')):
            self.logger.info('%016x %8x %8d %8d %8d %8d %8d %8d',
                             ev.msg.datapath.id, stat.port_no,
                             stat.rx_packets, stat.rx_bytes, stat.rx_errors,
                             stat.tx_packets, stat.tx_bytes, stat.tx_errors)

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