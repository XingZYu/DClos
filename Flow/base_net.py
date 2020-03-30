from mininet.net import Mininet
import time as pytime
import random
import sched
class BaseNet(Mininet):
    def iperf_single(self, hosts = None, bw = '10M', time = 1, port = 5001, log=False):
        if not hosts or len(hosts) != 2:
            return
        client, server = hosts
        servername = server.name
        clientname = client.name
        server_command = 'iperf -s -p ' + str(port) +' -i 1 > data/'
        client_command = 'iperf -t ' + str(time) + ' -c ' + server.IP() + ' -b ' + bw + ' -p ' + str(port) +' -i 1 > data/'
        server_command += servername + 'B' + clientname +'&'
        client_command += clientname +'T' + servername +'&'
        # if(log):
        #     server_command += servername + 'B' + clientname +'&'
        #     client_command += + clientname +'T' + servername +'&'
        # else:
        #     server_command += 'log'
        #     client_command += 'log'
        server.cmd(server_command)
        client.cmd(client_command)
        print clientname + '->' + servername + ' bw: ' + bw + ' port ' + str(port) 
        if(not log):
            return
        print clientname + '->' + servername
        print server_command
        print client_command
        # iperf -t 10 -c 10.0.0.2 -b 10M > client&

    def iperf_all_to_all(self, bw = '1M', time = 10):
        port = 5001
        host_list = [h for h in self.hosts]
        host_num = len(host_list)
        time_list = []
        for i in xrange(host_num - 1):
            for j in xrange(i, host_num):
                if(i != j):
                    self.iperf_single([host_list[i], host_list[j]], bw=bw, time =time, port=port)
                    port += 1
                    self.iperf_single([host_list[j], host_list[i]], bw=bw, time =time, port=port)
                    port += 1
                    time_list.append(pytime.time())
        pytime.sleep(time + 1)
        
    def mouse_flow(self, hosts = None, bw = '1M', time = 1, parallel = 30, port = 5001):
        if not hosts or len(hosts) != 2:
            return
        client, server = hosts
        server.cmd('iperf -s -p ' + str(port) +'-i 1' +'&')
        client.cmd('iperf -t ' + str(time) + ' -c ' + server.IP() + ' -b ' + bw + ' -P ' + str(parallel) +' -p ' + str(port) +' -i 1 ' + '&')

    def elephant_flow(self, hosts = None, bw = '100M', time = 10, parallel = 30, port = 5001):
        if not hosts or len(hosts) != 2:
            return
        client, server = hosts
        server.cmd('iperf -s -p ' + str(port) +'-i 10' +'&')
        client.cmd('iperf -t ' + str(time) + ' -c ' + server.IP() + ' -b ' + bw +' -p ' + str(port) +' -i 10 ' + '&')

    def mouse_elephant_flow(self):
        port = 5001
        host_list = [h for h in self.hosts]
        host_num = len(host_list)

        # elephant
        for client_id in xrange(host_num - 1):
            server_id = random.randint(0, host_num - 1)
            while server_id == client_id:
                server_id = random.randint(0, host_num - 1)
            self.elephant_flow([host_list[client_id], host_list[server_id]], bw='100M', time =10, port=port)
            port += 1

        # mouse
        for i in range(10):
            for client_id in xrange(host_num - 1):
                server_id = random.randint(0, host_num - 1)
                while server_id == client_id:
                    server_id = random.randint(0, host_num - 1)
                self.mouse_flow([host_list[client_id], host_list[server_id]], bw='1M', time =1, port=port)
                port += 1
            pytime.sleep(1)

    def simulate_traffic(self, traffic_arr, time_arr, log=False):
        if(len(traffic_arr) != len(time_arr)):
            print 'input data error: traffic and data no match'
            return
        length = len(traffic_arr)
        time = 0
        host_list = [h for h in self.hosts]
        host_num = len(host_list)
        schedule = sched.scheduler(pytime.time,pytime.sleep)
        port = 5001
        for n in range(length):
            for i in range(host_num):
                for j in range(host_num):
                    if(i != j):
                        flow_duration = time_arr[n]
                        flow = traffic_arr[n][i][j]
                        elephant_flow = flow *random.uniform(0.6, 0.9)
                        mouse_flow = flow - elephant_flow
                        mouse_num = random.randint(3,6)
                        mouse_flow /= mouse_num

                        #elephant_flow
                        schedule.enter(time, 1, self.iperf_single, ([host_list[i], host_list[j]], str(elephant_flow) + 'M', flow_duration, port, log))
                        port += random.randint(1, host_num)
                        #mouse_flow
                        mouse_time = time
                        mouse_duration = flow_duration / mouse_num
                        for mouse in range(mouse_num):
                            schedule.enter(mouse_time, 0, self.iperf_single, ([host_list[i], host_list[j]], str(mouse_flow) + 'M', mouse_duration, port, log))
                            port += random.randint(1, host_num)
                            mouse_time += mouse_duration
            time += time_arr[n]
        schedule.run()
        
