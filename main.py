from Flow.base_net import BaseNet
from topo.simple_clos import SimpleClos
from mininet.log import setLogLevel
from SFlow.enable_sflow import EnableSFlow

def simpleTest():
    topo = SimpleClos()
    net = BaseNet(topo)
    net.start()
    EnableSFlow(net)
    net.iperf_all_to_all(time= 3)
    print 'waiting'
    net.stop()

if __name__ == '__main__':
    # Tell mininet to print useful information
    setLogLevel('info')
    simpleTest()
