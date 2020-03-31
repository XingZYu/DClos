import time, random
from ryu.base import app_manager
from operator import attrgetter
from collections import defaultdict
from ryu.app import simple_switch_13
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_5, ofproto_v1_3, ofproto_v1_4
from ryu.lib.packet import packet
from ryu.lib.packet import *
from ryu.lib.packet import ether_types
from ryu.lib import hub
from ryu.topology import event
import sys, os
import json

sys.path.append(os.getcwd())

REFERENCE_BW = 10000000

DEFAULT_BW = 10000000

MAX_PATHS = 2

MAX_GROUPS = 10000

class DC_Switch(app_manager.RyuApp):
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION,
                    ofproto_v1_5.OFP_VERSION,
                    ofproto_v1_4.OFP_VERSION]

    """
    Multipath Controller

    ================ ========================= ==============================
    Attribute        Key                       Value
    ================ ========================= ==============================
    arp_table        IP Address                Mac Address
    hosts            Mac Address               (Dpid, Port)
    dp_list
    switches         /                         Switch ID
    adjacency        (Dpid1, Dpid2)            Port
    bandwidths      
    groud_ids        (node, Src_IP, Dst_IP)    
    port_bucket      (Dpid, Port)              List of (group_id, bucket_id)
    ================ ========================= ==============================

    """
    def __init__(self, *args, **kwargs):
        super(DC_Switch, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        self.arp_table = {}
        self.hosts = {}
        self.dp_list = {}
        self.switches = []
        self.multipath_groups = {}
        self.FF_groups = {}
        self.adjacency = defaultdict(dict)
        self.bandwidths = defaultdict(lambda: defaultdict(lambda: DEFAULT_BW))
        self.port_bucket = defaultdict(lambda: defaultdict(lambda: []))

    def get_paths(self, src, dst):
        '''
        Get all paths from src to dst using DFS algorithm    
        '''
        if src == dst:
            # host target is on the same switch
            return [[src]]
        paths = []
        stack = [(src, [src])]
        while stack:
            (node, path) = stack.pop()
            for next_dp in set(self.adjacency[node].keys()) - set(path):
                if next_dp is dst:
                    paths.append(path + [next_dp])
                else:
                    stack.append((next_dp, path + [next_dp]))
        self.logger.info("Available paths from %s to %s : %s", src, dst, paths)
        self.logger.info(self.adjacency)
        return paths

    def get_link_cost(self, s1, s2):
        '''
        Get the link cost between two switches 
        '''
        e1 = self.adjacency[s1][s2]
        e2 = self.adjacency[s2][s1]
        bl = min(self.bandwidths[s1][e1], self.bandwidths[s2][e2])
        ew = REFERENCE_BW/bl
        return ew

    def get_path_cost(self, path):
        '''
        Get the path cost
        '''
        cost = 0
        for i in range(len(path) - 1):
            cost += self.get_link_cost(path[i], path[i+1])
        return cost

    def get_optimal_paths(self, src, dst):
        '''
        Get the n-most optimal paths according to MAX_PATHS
        '''
        paths = self.get_paths(src, dst)
        paths_count = len(paths) if len(
            paths) < MAX_PATHS else MAX_PATHS
        return sorted(paths, key=lambda x: self.get_path_cost(x))[0:(paths_count)]

    def add_ports_to_paths(self, paths, first_port, last_port):
        '''
        Add the ports that connects the switches for all paths
        '''
        paths_p = []
        for path in paths:
            p = {}
            in_port = first_port
            for s1, s2 in zip(path[:-1], path[1:]):
                out_port = self.adjacency[s1][s2]
                p[s1] = (in_port, out_port)
                in_port = self.adjacency[s2][s1]
            p[path[-1]] = (in_port, last_port)
            paths_p.append(p)
        return paths_p

    def generate_openflow_gid(self, group_type = 'SELECT'):
        '''
        Returns a OpenFlow group id
        '''
        if group_type == 'SELECT':
            if len(self.multipath_groups) == MAX_GROUPS:
                raise Exception('Maximum group number reached')
            return len(self.multipath_groups) + 1
        else:
            return MAX_GROUPS + len(self.FF_groups) + 1

    def install_paths(self, src, first_port, dst, last_port, ip_src, ip_dst):
        computation_start = time.time()
        paths = self.get_optimal_paths(src, dst)
        # self.logger.info(paths)
        if len(paths) == 0:
            return None
        pw = []
        for path in paths:
            pw.append(self.get_path_cost(path))
            self.logger.debug("%s cost = %s", path, pw[-1])
        sum_of_pw = sum(pw) * 1.0
        paths_with_ports = self.add_ports_to_paths(paths, first_port, last_port)
        switches_in_paths = set().union(*paths)

        for node in switches_in_paths:

            dp = self.dp_list[node]
            ofp = dp.ofproto
            ofp_parser = dp.ofproto_parser

            ports = defaultdict(list)
            actions = []
            i = 0

            for path in paths_with_ports:
                if node in path:
                    in_port = path[node][0]
                    out_port = path[node][1]
                    if (out_port, pw[i]) not in ports[in_port]:
                        ports[in_port].append((out_port, pw[i]))
                i += 1

            for in_port in ports:

                match_ip = ofp_parser.OFPMatch(
                    eth_type=0x0800, 
                    in_port=in_port,
                    ipv4_src=ip_src, 
                    ipv4_dst=ip_dst
                )
                match_arp = ofp_parser.OFPMatch(
                    eth_type=0x0806,
                    in_port=in_port, 
                    arp_spa=ip_src, 
                    arp_tpa=ip_dst
                )

                out_ports = ports[in_port]

                if len(out_ports) > 1:
                    group_id = None
                    group_new = False

                    if (node, src, dst) not in self.multipath_groups:
                        group_new = True
                        self.multipath_groups[
                            node, src, dst] = self.generate_openflow_gid()
                    group_id = self.multipath_groups[node, src, dst]

                    buckets = []
                    for i in range(len(out_ports)):
                        ff_group_new = False
                        (port, weight) = out_ports[i]
                        if (node, src, dst, port) not in self.FF_groups: 
                            ff_group_new = True
                            self.FF_groups[
                                node, src, dst, port] = self.generate_openflow_gid(
                                        group_type = 'FF'
                                        )
                        ff_group_id = self.FF_groups[node, src, dst, port]
                        ff_action = [ofp_parser.OFPActionOutput(port)]
                        ff_bucket = [ofp_parser.OFPBucket(
                                watch_port = port,
                                actions = ff_action
                                )]
                        for j in range(len(out_ports)):
                            if j == i:
                                continue
                            ff_action = [ofp_parser.OFPActionOutput(out_ports[j][0])]
                            ff_bucket.append(
                                ofp_parser.OFPBucket(
                                    watch_port = out_ports[j][0],
                                    actions = ff_action
                                    )
                                )
                        bucket_weight = int(round((1 - weight/sum_of_pw) * 10))
                        bucket_action = [ofp_parser.OFPActionGroup(ff_group_id)]
                        buckets.append(
                            ofp_parser.OFPBucket(
                                weight=1,
                                actions=bucket_action
                            )
                        )
                        
                        self.logger.info(dir(buckets[-1]))
                        bucket_id = buckets[-1].bucket_id
                        self.port_bucket[dpid][port].append((group_id, bucket_id))

                        if ff_group_new:
                            req = ofp_parser.OFPGroupMod(
                                dp, ofp.OFPGC_ADD, ofp.OFPGT_FF, ff_group_id,
                                ff_bucket
                            )
                            dp.send_msg(req)

                        else:
                            req = ofp_parser.OFPGroupMod(
                                dp, ofp.OFPGC_MODIFY, ofp.OFPGT_FF,
                                ff_group_id, ff_bucket)
                            dp.send_msg(req)

                    if group_new:
                        req = ofp_parser.OFPGroupMod(
                            dp, ofp.OFPGC_ADD, ofp.OFPGT_SELECT, group_id,
                            buckets
                        )
                        dp.send_msg(req)
                    else:
                        req = ofp_parser.OFPGroupMod(
                            dp, ofp.OFPGC_MODIFY, ofp.OFPGT_SELECT,
                            group_id, buckets)
                        dp.send_msg(req)

                    actions = [ofp_parser.OFPActionGroup(group_id)]

                    self.add_flow(dp, 32768, match_ip, actions)
                    self.add_flow(dp, 1, match_arp, actions)

                elif len(out_ports) == 1:
                    port = out_ports[0][0]
                    ff_group_new = False
                    if (node, src, dst, port) not in self.FF_groups: 
                        ff_group_new = True
                        self.FF_groups[
                            node, src, dst, port] = self.generate_openflow_gid(
                                group_type = 'FF'
                                )
                    ff_group_id = self.FF_groups[node, src, dst, port]
                    ff_action = [ofp_parser.OFPActionOutput(port)]
                    ff_bucket = [ofp_parser.OFPBucket(
                            watch_port = port,
                            actions = ff_action
                            )]
                    # ff_action = [ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                    #                       ofp.OFPCML_NO_BUFFER)]
                    # This can lead to unexplianable problem

                    ff_action = [ofp_parser.OFPActionGroup(0)]
                    ff_bucket.append(ofp_parser.OFPBucket(
                        watch_port = in_port,
                        actions = ff_action
                    ))

                    if ff_group_new:
                        req = ofp_parser.OFPGroupMod(
                            dp, ofp.OFPGC_ADD, ofp.OFPGT_FF, ff_group_id,
                            ff_bucket
                        )
                        dp.send_msg(req)

                    else:
                        req = ofp_parser.OFPGroupMod(
                            dp, ofp.OFPGC_MODIFY, ofp.OFPGT_FF,
                            ff_group_id, ff_bucket)
                        dp.send_msg(req)

                    actions = [ofp_parser.OFPActionGroup(ff_group_id)]
                    self.add_flow(dp, 32768, match_ip, actions)
                    self.add_flow(dp, 1, match_arp, actions)
        # print "Path installation finished in ", time.time() - computation_start 
        return paths_with_ports[0][src][1]

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

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        
        bucket = [parser.OFPBucket(
            actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                              ofproto.OFPCML_NO_BUFFER)]
        )]
        req = parser.OFPGroupMod(
                            datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_INDIRECT,
                            0, bucket)
        datapath.send_msg(req)
        self.add_flow(datapath, 0, match, actions)

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_stats_reply_handler(self, ev):
        switch = ev.msg.datapath
        for p in ev.msg.body:
            # Openflow15i
            self.logger.info(p.properties)
            self.bandwidths[switch.id][p.port_no] = p.properties[0].curr_speed
            # Openflow13
            # self.bandwidths[switch.id][p.port_no] = p.curr_speed

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # If you hit this you might want to increase
        # the "miss_send_length" of your switch
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
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

        if src not in self.hosts:
            self.hosts[src] = (dpid, in_port)
        
        out_port = ofproto.OFPP_FLOOD

        self.logger.info("packet in %s %s %s %s %s", dpid, src, dst, in_port, eth.ethertype)

        if arp_pkt:
            src_ip = arp_pkt.src_ip
            dst_ip = arp_pkt.dst_ip
            if arp_pkt.opcode == arp.ARP_REPLY:
                self.arp_table[src_ip] = src
                h1 = self.hosts[src]
                h2 = self.hosts[dst]
                out_port = self.install_paths(h1[0], h1[1], h2[0], h2[1], src_ip, dst_ip)
                if out_port == None:
                    return 
                self.install_paths(h2[0], h2[1], h1[0], h1[1], dst_ip, src_ip)
            elif arp_pkt.opcode == arp.ARP_REQUEST:
                if dst_ip in self.arp_table:
                    self.arp_table[src_ip] = src
                    dst_mac = self.arp_table[dst_ip]
                    h1 = self.hosts[src]
                    h2 = self.hosts[dst_mac]
                    out_port = self.install_paths(h1[0], h1[1], h2[0], h2[1], src_ip, dst_ip)
                    if out_port == None:
                        return 
                    self.install_paths(h2[0], h2[1], h1[0], h1[1], dst_ip, src_ip) # reverse
        
        elif eth.ethertype == ether_types.ETH_TYPE_IP:
            ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
            src_ip = ipv4_pkt.src
            dst_ip = ipv4_pkt.dst
            self.arp_table[src_ip] = src
            h1 = self.hosts[src]
            h2 = self.hosts[dst]
            self.install_paths(h1[0], h1[1], h2[0], h2[1], src_ip, dst_ip)
            self.install_paths(h2[0], h2[1], h1[0], h1[1], dst_ip, src_ip)

        actions = [parser.OFPActionOutput(out_port)]

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data=data)
        datapath.send_msg(out)
    
    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, ev):
        switch = ev.switch.dp
        ofp_parser = switch.ofproto_parser

        if switch.id not in self.switches:
            self.switches.append(switch.id)
            self.dp_list[switch.id] = switch

            # Request port/link descriptions, useful for obtaining bandwidth
            req = ofp_parser.OFPPortDescStatsRequest(switch)
            switch.send_msg(req)

    @set_ev_cls(event.EventSwitchLeave, MAIN_DISPATCHER)
    def switch_leave_handler(self, ev):
        switch = ev.switch.dp.id
        if switch in self.switches:
            self.switches.remove(switch)
            del self.dp_list[switch]
            del self.adjacency[switch]

    @set_ev_cls(event.EventLinkAdd, MAIN_DISPATCHER)
    def link_add_handler(self, ev):
        s1 = ev.link.src
        s2 = ev.link.dst
        self.logger.info("Link add: %s %s", s1.dpid, s2.dpid)
        self.adjacency[s1.dpid][s2.dpid] = s1.port_no
        self.adjacency[s2.dpid][s1.dpid] = s2.port_no

    @set_ev_cls(event.EventLinkDelete, MAIN_DISPATCHER)
    def link_delete_handler(self, ev):
        s1 = ev.link.src
        s2 = ev.link.dst
        self.logger.info("Link delete: %s %s", s1.dpid, s2.dpid)
        # Exception handling if switch already deleted
        try:
            del self.adjacency[s1.dpid][s2.dpid]
            del self.adjacency[s2.dpid][s1.dpid]
        except KeyError:
            pass

