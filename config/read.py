#python3
# coding=utf-8

import json
 
# with open("./config.json",'r') as load_f:
#     load_dict = json.load(load_f)

# def read_topo(file = "./topo.json"):
#     with open(file, 'r') as load_f:
#         load_dict = json.load(load_f)
    
#     print(load_dict)

def read_topo(file = "./topo.json"):
    switch_list = ['null']
    switch_dict = {}
    switch_port = {}
    
    id = 0
    # two switch have at most one link
    with open(file, 'r') as load_f:
            load_dict = json.load(load_f)
    
    for pod in load_dict['pod_list']:
        id +=  1
        # d = {'iprange':(ip,mask),'host':{ip:port},'switch':{switchid:port}, 'id':switchid}
        d = {'host':{},'switch':{}}
        switch_dict[pod['name']] = d
        switch_list.append(d)
        d['ip'] = (pod['ip_range'], pod['ip_mask'])
        d['id'] = id
        switch_port[pod['name']] = 0
        for host in pod["host_list"]:
            switch_port[pod['name']] += 1
            d['host'][host['ip']] = switch_port[pod['name']]
    
    for link in load_dict['link_graph']:
        switch_port[link['begin']] += 1
        switch_port[link['end']] += 1
        switch_dict[link['begin']]['switch'][switch_dict[link['end']]['id']] =  switch_port[link['begin']]
        switch_dict[link['end']]['switch'][switch_dict[link['begin']]['id']] =  switch_port[link['end']]
    
    return switch_list


# for i in read_topo():
#     print i