from mininet.net import Mininet
from mininet.util import quietRun
from requests import put
from os import listdir, environ
import re
import socket
import fcntl
import array
import struct
import sys

def EnableSFlow(net):
  def getIfInfo(dst):
    is_64bits = sys.maxsize > 2**32
    struct_size = 40 if is_64bits else 32
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    max_possible = 8 # initial value
    while True:
      bytes = max_possible * struct_size
      names = array.array('B')
      for i in range(0, bytes):
        names.append(0)
      outbytes = struct.unpack('iL', fcntl.ioctl(
        s.fileno(),
        0x8912,  # SIOCGIFCONF get interface list
        struct.pack('iL', bytes, names.buffer_info()[0]) # buffer_info returns (address, length)
      ))[0]
      if outbytes == bytes:
        max_possible *= 2
      else:
        break
    namestr = names.tostring()
    # namestr: the list of all interfaces
    # s.connect( (hostname, port) )
    s.connect((dst, 0))
    ip = s.getsockname()[0]
    for i in range(0, outbytes, struct_size):
      name = namestr[i:i+16].split('\0', 1)[0]
      addr = socket.inet_ntoa(namestr[i+20:i+24])
      if addr == ip:
        return (name,addr)
  
  def configSFlow(net,collector,ifname,sampling,polling):
    print "*** Enabling sFlow:"
    sflow = 'ovs-vsctl -- --id=@sflow create sflow agent=%s target=%s sampling=%s polling=%s --' % (ifname,collector,sampling,polling)
    for s in net.switches:
      sflow += ' -- set bridge %s sflow=@sflow' % s
    print ' '.join([s.name for s in net.switches])
    quietRun(sflow)

  collector = environ.get('COLLECTOR','127.0.0.1') # 127.0.0.1 default
  sampling = environ.get('SAMPLING','10')
  polling = environ.get('POLLING','10')
  ifname = getIfInfo(collector)[0]
  
  configSFlow(net,collector,ifname,sampling,polling)
  
