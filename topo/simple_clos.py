from mininet.topo import Topo

class SimpleClos(Topo):
    '''
    simple three layer clos topology, only consider the
    intra-cluster traffic
    '''

    def build(self, tor_num = 2, host_num = 1, pod_num = 1):
        tors = []
        pods = []
        host_bw = 10
        tor_bw = 10

       #add pod sw
        for i in range(pod_num):
           sw = self.addSwitch('p{}'.format(i + 1))
           pods.append(sw)

        #add tor sw and host
        for i in range(tor_num):
            sw = self.addSwitch('tor{}'.format(i + 1))
            tors.append(sw)
            for j in range(host_num):
                host = self.addHost('t{}_h{}'.format(i + 1, j + 1))
                self.addLink(sw, host, bw = host_bw)
        
        #link tor sw and pod sw

        for pod_sw in pods:
            for tor_sw in tors:
                self.addLink(pod_sw, tor_sw, bw = tor_bw)


if __name__ == "__main__":
    topos = {'SimpleClos' : (lambda: SimpleClos()) }




