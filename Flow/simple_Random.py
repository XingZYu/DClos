import time as pytime
import sched
import random
class Test:
    def __init__(self):
        self.hosts = ['h1','h2']

    def iperf_single(self, hosts = None, bw = '10M', time = 1, port = 5001):
        if not hosts or len(hosts) != 2:
            return
        client, server = hosts
        servername = server
        clientname = client
        print clientname + '->' + servername + ' bw: ' + bw + ' port ' + str(port) 

    def simulate_traffic(self, traffic_arr, time_arr):
        print 'simulation'
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
                        print flow
                        elephant_flow = flow *random.uniform(0.6, 0.9)
                        mouse_flow = flow - elephant_flow
                        mouse_num = random.randint(3,6)
                        mouse_flow /= mouse_num

                        #elephant_flow
                        schedule.enter(time, 1, self.iperf_single, ([host_list[i], host_list[j]], str(elephant_flow) + 'M', flow_duration, port))
                        port += random.randint(1, host_num)
                        #mouse_flow
                        mouse_time = time
                        mouse_duration = flow_duration / mouse_num
                        for mouse in range(mouse_num):
                            schedule.enter(mouse_time, 0, self.iperf_single, ([host_list[i], host_list[j]], str(mouse_flow) + 'M', mouse_duration, port))
                            port += random.randint(1, host_num)
                            mouse_time += mouse_duration
            time += time_arr[n]
        schedule.run()

# import numpy as np
# traffic_arr = [np.random.rand(3,3)]
# time_arr = [10]
# print(traffic_arr)

# a = Test()
# a.simulate_traffic(traffic_arr, time_arr)

print [[10 for i in range(8)] for j in range(8)]