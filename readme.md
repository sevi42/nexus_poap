# nexus_poap

## Synopsis

Adapted integration for poap for nexus 93120TX

## Installation

You need a dhcp server + http server

````
#DHCP POAP cisco n9k
subnet 10.0.0.0 netmask 255.255.255.0 {
  option routers 10.0.0.1;
  option tftp-server-name "http://x.x.x.x";
  option bootfile-name "/cisco/n9k/poap/93120TX_poap.py";
  pool {
       range 10.42.31.100 10.42.31.200;
       default-lease-time 3600;
       min-lease-time 3600;
       max-lease-time 3600;
   }
}
````

You also need a http server with this file tree

````
cisco
└── n9k
    ├── cnf
    │ └── <cdp_router_name>
    │     ├── Ethernet1_19
    │     ├── Ethernet1_20
    │     ├── Ethernet1_5
    │     ├── Ethernet1_6
    ├── img
    │ ├── n9000-epld.7.0.3.I2.2e.img
    │ └── nxos.7.0.3.I2.2e.bin
    └── poap
        ├── 93120TX_poap.py
        ├── 93120TX_poap.py.md5
        ├── build.sh
        ├── readme.md
````


Poap script will look for the version and then the config based on top switch/router cdp name and remote port name
