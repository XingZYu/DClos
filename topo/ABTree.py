import networkx as nx
import copy
import json

class ABTree:

    _swcnt = 0
    _hostcnt = 0
    _podcnt = 0

    def __init__(self, k, L):
        self._portcnt = k
        self._layer = L
        self.tree = self._buildtree(k, L)[0]
        self._add_ports()
        self.ryu_tree = self._transform()

    def _transform(self):
        mapping = {}
        for node in self.tree.nodes:
            if node[0] == 's':
                mapping[node] = int(node[1:])
            else:
                mapping[node] = self.tree.nodes[node]['ip']
        return nx.relabel_nodes(self.tree, mapping)

    def _buildtree(self, k, L, base_ip = ['10', '0', '0', '0']): 

        if L < 2 or L > 4:
            raise Exception("Invalid layer number: {}, which should be in range [2, 4]".format(L))

        if L == 2:
            return self._basetree(k, base_ip)
        
        n = k // 2
        top_n = n << (L - 2)
        G = nx.Graph()
        top_sws = []
        for i in range(top_n):
            self._swcnt += 1
            sw_name = 's{}'.format(self._swcnt)
            G.add_node(sw_name, layer = L, pod = 0)
            top_sws.append(sw_name)

        base_ip[4 - L] = str(int(base_ip[4 - L]) + 1)
        Atree, A_sws = self._buildtree(k, L-1, base_ip)
        
        base_ip[4 - L] = str(int(base_ip[4 - L]) + 1)
        Btree, B_sws = self._buildtree(k, L-1, base_ip)

        child = nx.union(Atree, Btree)
        G = nx.union(G, child)

        for i in range(len(A_sws)):
            a_sw = A_sws[i]
            for j in range(k // 2):
                G.add_edge(a_sw, top_sws[i * (k // 2) + j])

        for i in range(len(B_sws)):
            b_sw = B_sws[i]
            for j in range(k // 2):
                G.add_edge(b_sw, top_sws[j * (top_n // 2) + i])
        
        return G, top_sws

    def _basetree(self, k, base_ip):
        G = nx.Graph()
        top_sws = []
        ip_list = copy.copy(base_ip)
        ip_range = '.'.join(base_ip)
        idx = self._swcnt
        self._podcnt += 1

        for i in range(k//2):
            self._swcnt += 1
            sw_name = 's{}'.format(self._swcnt)
            top_sws.append(sw_name)
            G.add_node(
                sw_name, layer = 2, pod = self._podcnt, 
                ip_range = ip_range, 
                ip_mask = "255.255.0.0")

        for i in range(k//2):
            self._hostcnt += 1
            self._swcnt += 1
            ip_list[2] = str(int(ip_list[2]) + 1)
            host_ip = '.'.join(ip_list)
            host_name = 'h{}'.format(self._hostcnt)
            sw_name = 's{}'.format(self._swcnt)
            G.add_node(host_name, ip = host_ip, pod = self._podcnt, layer = 0)
            G.add_node(
                sw_name, layer = 1, pod = self._podcnt,
                ip_range = host_ip,
                ip_mask = "255.255.255.0"
                )
            G.add_edge(host_name, sw_name)
            for j in range(idx, idx + k//2):
                G.add_edge(sw_name, 's{}'.format(j+1))

        return G, top_sws

    def _add_ports(self):
        adj_mat = {}
        for node in list(self.tree.nodes):
            curr_layer = self.tree.nodes[node]['layer']
            adj_nodes = [[n, self.tree.nodes[n]['layer']] 
                            for n in self.tree.adj[node]]

            adj_nodes.sort(key = lambda x : x[1])
            
            port_num = 1
            
            for a_node in adj_nodes:
                if a_node[1] < curr_layer or node[0] == 'h':
                    a_node[1] = port_num
                else:
                    if port_num <= self._portcnt // 2:
                        port_num = self._portcnt // 2 + 1
                    a_node[1] = port_num
                port_num += 1
            
            adj_nodes_dict = {item[0] : item[1] for item in adj_nodes}

            adj_mat[node] = adj_nodes_dict
        
        for edge in self.tree.edges:
            self.tree.edges[edge]['port1'] = adj_mat[edge[0]][edge[1]]
            self.tree.edges[edge]['port2'] = adj_mat[edge[1]][edge[0]]

        print(self.tree['s1']['s5'], self.tree['s5']['s1'])
        
    def show(self):
        # print(dict(self.tree.nodes))
        nodes_dict = dict(self.tree.nodes)
        
        with open('./topo/nodes.json', 'w') as f:
            json.dump(nodes_dict, f)
        
        with open('./topo/edges.json', 'w') as f:
            json.dump(list(self.tree.edges), f)

        print(self.tree.nodes.data())
        print(list(self.tree.edges))

if __name__ == "__main__":
    abtree = ABTree(4, 3)
    abtree.show()
