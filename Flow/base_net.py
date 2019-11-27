from mininet.net import Mininet
import time as pytime
class BaseNet(Mininet):
    def iperf_single(self, hosts = None, bw = '10M', time = 1, port = 5001):
        if not hosts or len(hosts) != 2:
            return
        client, server = hosts
        servername = server.name
        clientname = client.name
        print clientname + '->' + servername
        
        server.cmd('iperf -s -p ' + str(port) +'-i 1 > data/' + servername + 'B' + clientname +'&')
        # print 'iperf -s -p ' + str(port) +'-i 1 > data/' + servername + 'B' + clientname +'&'
        client.cmd('iperf -t ' + str(time) + ' -c ' + server.IP() + ' -b ' + bw + ' -p ' + str(port) +' -i 1 > data/' + clientname +'T' + servername +'&')
        # print 'iperf -t ' + str(time) + ' -c ' + server.IP() + ' -b ' + bw + ' -p ' + str(port) +' -i 1 > data/' + clientname +'T' + servername +'&'
        # iperf -t 10 -c 10.0.0.2 -b 10M > client&

    def iperf_all_to_all(self, bw = '1M', time = 10):
        port = 5001
        host_list = [h for h in self.hosts]
        host_num = len(host_list)
        for i in xrange(host_num - 1):
            for j in xrange(i, host_num):
                if(i != j):
                    self.iperf_single([host_list[i], host_list[j]], bw=bw, time =time, port=port)
                    port += 1
                    self.iperf_single([host_list[j], host_list[i]], bw=bw, time =time, port=port)
                    port += 1
        pytime.sleep(time + 1)
        
