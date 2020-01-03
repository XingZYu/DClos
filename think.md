# think

use iperf to create traffic, reference:

https://www.sdnlab.com/11079.html

learn iperf command in this site:
https://man.linuxde.net/iperf

costum topology and net test like this:

```python
class MyTopo( Topo ):
   def build( self, ...):
def myTest( net ):
...

topos = { 'mytopo': MyTopo }
tests = { 'mytest': myTest }
```
and then in the bash to test:

```bash
sudo mn --custom mytopo.py,mytest.py --topo mytopo,3 --test mytest
```

I prefer this method because we can modify some varible when run the test;

reference:
https://github.com/mininet/mininet/wiki/Introduction-to-Mininet

udp:

```bash
iperf -u -t 10 -c 10.0.0.2 -b 10M > client&
iperf -u -s -i 1 > server&
```

tcp:

```bash
iperf -t 10 -c 10.0.0.2 -b 10M > client&
iperf -s -i 1 > server&
```

flow table:

```python
# gototable
match = parser.OFPMatch()
inst = [parser.OFPInstructionGotoTable(table_id=2)]
mod = parser.OFPFlowMod(datapath=datapath, priority=5, match=match, instructions=inst)
datapath.send_msg(mod)


OFPFC_MODIFY可以, 但是DELETE不行

要先有group 才能gotogroup

OFPFC_MODIFY 可以直接更新整个group table

```
