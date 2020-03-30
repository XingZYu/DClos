import json
from itertools import combinations

def create_pod_datacenter(pod_num):
    switch_list = [f's{i}' for i in range(1, pod_num + 1)]
    host_name_list = [f's{i}h1' for i in range(1, pod_num + 1)]
    ip_range_list = [f'10.0.{i}.0' for i in range(1, pod_num + 1)]
    ip_mask = '255.255.255.0'
    host_ip_list = [f'10.0.{i}.1' for i in range(1, pod_num + 1)]
    host_mac_list = ['00:00:00:00:00:' + str(i).rjust(2,'0') for i in range(1, pod_num + 1)]

    pod_list = []
    for i in range(pod_num):
        item = {
            "name": switch_list[i],
            "ip_range": ip_range_list[i],
            "ip_mask": ip_mask,
            "host_list": [
                {
                    "name": host_name_list[i],
                    "ip": host_ip_list[i],
                    "mac": host_mac_list[i],
                }
            ],
        }
        pod_list.append(item)

    link_list = list(combinations(switch_list, 2))
    link_graph = []
    for (begin, end) in link_list:
        link_graph.append({
            "begin": begin,
            "end": end,
        })
    
    res = {
        "pod_list": pod_list,
        "link_graph": link_graph,
    }

    with open(f"./{pod_num}pod_topo.json", "w") as f:
        json.dump(res, f)

if __name__ == "__main__":
    create_pod_datacenter(8)
