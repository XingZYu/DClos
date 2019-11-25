# d = {'a':1}
# d2 = {'x': d}
# l = []
# l.append(d)
# d['b'] = 2
# d = {}
# d['a'] = 4
# print d2
# print l

import json
file = '../config/topo.json'
switch_list = ['null']
switch_dict = {}
switch_port = {}
ip_dict = {}
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


for key in switch_dict:
    print key, switch_dict[key]

print ("-------------------")

for i in switch_list:
    print i