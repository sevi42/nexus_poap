#!/bin/env python
#md5sum="f3e2f1aad432768a76fd66e60abc1f8a"
# Still needs to be implemented.
# Return Values:
# 0 : Reboot and reapply configuration
# 1 : No reboot, just apply configuration. Customers issue copy file run ; copy
# run start. Do not use scheduled-config since there is no reboot needed. i.e.
# no new image was downloaded
# -1 : Error case. This will cause POAP to restart the DHCP discovery phase.

# The above is the (embedded) md5sum of this file taken without this line,
# can be # created this way:
# f=93120TX_poap.py ; cat $f | sed '/^#md5sum/d' > $f.md5 ; sed -i "s/^#md5sum=.*/#md5sum=\"$(md5sum $f.md5 | sed 's/ .*//')\"/" $f
# This way this script's integrity can be checked in case you do not trust
# tftp's ip checksum. This integrity check is done by /isan/bin/poap.bin).
# The integrity of the files downloaded later (images, config) is checked
# by downloading the corresponding file with the .md5 extension and is
# done by this script itself.

import os
import re
import shutil
import signal
import string
import sys
import time

from cli import *
from nxos import *

# version used on 93120TX
n9k_img_file = "nxos.7.0.3.I2.2e.bin"
n9k_img_file_epld = "n9000-epld.7.0.3.I2.2e.img"
n9k_dl_img_url = 'http://10.43.0.3/cisco/n9k/img/'
n9k_dl_cnf_url = 'http://10.43.0.3/cisco/n9k/cnf/'
tmp_dst_cnf = 'volatile:poap.cfg'
min_cnf_size = 10000
required_space = 350000

# static vrf if not defined by poap
vrf = "management"
if os.environ.has_key('POAP_VRF'):
    vrf = os.environ['POAP_VRF']

# Static uplink interface if not defined by poap
cdp_interface = 'Eth1/97'
if os.environ.has_key('POAP_INTF'):
    cdp_interface = os.environ['POAP_INTF']

# pid
pid = ""
if os.environ.has_key('POAP_PID'):
    pid = os.environ['POAP_PID']

# log buffer
poap_log_file = ""
enable_syslog = 1

# signal handling
def sig_handler_no_exit(signum, frame):
    poap_log("INFO: SIGTERM Handler while configuring boot variables")

def sigterm_handler(signum, frame):
    poap_log("INFO: SIGTERM Handler")
    abort_cleanup_exit()
    exit(1)

# Poap logs
def init_poap_log():
    t = time.localtime()
    now = "%d_%d_%d" % (t.tm_hour, t.tm_min, t.tm_sec)
    log_filename = "/bootflash/poap.log"
    if now is None:
        now = cli("show clock | sed 's/[ :]/_/g'")
    try:
        log_filename = "%s.%s" % (log_filename, now)
    except Exception as inst:
        print inst
    poap_log_file = open(log_filename, "w+")
    return poap_log_file

def poap_log(info):
    poap_log_file.write(info)
    poap_log_file.write("\n")
    poap_log_file.flush()
    print "poap_py_log:" + info
    if enable_syslog:
        py_syslog(1, 'POAP_LOG: %s' % str(info))
    sys.stdout.flush()

def poap_log_close():
    poap_log_file.close()

# Clean exist fct
def abort_cleanup_exit():
    poap_log("INFO: cleaning up")
    poap_log_close()
    exit(-1)

# Cmd utils
def run_cli(cmd):
    poap_log("CLI : %s" % cmd)
    return cli(cmd)

def delete_file(filename):
    try:
        cli("delete %s" % filename)
    except:
        pass

# Check nxos version
def check_nx_version():
    poap_log("INFO: Checking if given version is up to date")
    try:
        ret = clid("show version")
    except:
        poap_log("ERROR: Can't get switch version")
        abort_cleanup_exit()
    jret = json.loads(ret)
    nxos_version = jret['kick_file_name'].split('/')[3]
    poap_log("INFO: found nx_os version :%s" %nxos_version)
    if nxos_version == n9k_img_file:
        poap_log("INFO: Version is up to date")
        return 1
    poap_log("INFO: Version is outdated, pushing nxos %s" %n9k_img_file)
    return 0

# get nxos version with epld
def get_nxos_image(fatal=True):
    nxos_filename = 'bootflash:'+n9k_img_file
    epld_filename = 'bootflash:'+n9k_img_file_epld

    delete_file(nxos_filename)
    delete_file(epld_filename)
    cmd =  "terminal dont-ask ; copy %s%s bootflash: vrf %s" %(n9k_dl_img_url, n9k_img_file, vrf)
    try:
        run_cli(cmd)
    except:
        poap_log("WARN: Copy Failed: %s" % str(sys.exc_value).strip('\n\r'))
        if fatal:
            poap_log("ERROR: aborting")
            abort_cleanup_exit()
    cmd =  "terminal dont-ask ; copy %s%s bootflash: vrf %s" %(n9k_dl_img_url, n9k_img_file_epld, vrf)
    try:
        run_cli(cmd)
    except:
        poap_log("WARN: Copy Failed: %s" % str(sys.exc_value).strip('\n\r'))
        if fatal:
            poap_log("ERROR: aborting")
            abort_cleanup_exit()
    return 0

# Verify free space
def verify_freespace(): 
    freespace = int(cli("dir bootflash: | last 3 | grep free | sed 's/[^0-9]*//g'").strip('\n'))
    freespace = freespace / 1024
    poap_log("INFO: free space is %s kB"  % freespace )

    if required_space > freespace:
        poap_log("ERROR: Not enough space to copy the config, kickstart image and system image, aborting!")
        abort_cleanup_exit()

# Get information about cdp nei to get which config to get
def get_cdp_inf():
    poap_log("INFO: show cdp neighbors interface %s" % cdp_interface)
    try:
        a = clid("show cdp neighbors interface %s" % cdp_interface)
    except:
        poap_log("ERROR: Can't get cdp informations")
        abort_cleanup_exit()
    b = json.loads(a)
    # Split to avoir SR number
    cdpnei_switchName = str(b['TABLE_cdp_neighbor_brief_info']['ROW_cdp_neighbor_brief_info']['device_id']).split('(')[0]
    cdpnei_intfName = str(b['TABLE_cdp_neighbor_brief_info']['ROW_cdp_neighbor_brief_info']['port_id'])
    cdpnei_intfName = string.replace(cdpnei_intfName, "/", "_")
    if not cdpnei_switchName or not cdpnei_intfName:
        poap_log("ERROR: Can't get cdp switchName or cdp intfName")
        abort_cleanup_exit()
    poap_log("INFO: Found uplink CDP interface %s on remote switch : %s" %(cdpnei_switchName, cdpnei_intfName))
    return [cdpnei_switchName, cdpnei_intfName]
    
def get_sw_config(swName, ifName, fatal=True):
    full_config_url = n9k_dl_cnf_url + swName + '/' + ifName
    delete_file(tmp_dst_cnf)
    poap_log("INFO: Copying config")
    cmd = "terminal dont-ask ; copy %s %s vrf %s" %(full_config_url, tmp_dst_cnf, vrf) 
    try:
        run_cli(cmd)
    except:
        poap_log("WARN: Copy Failed: %s" % str(sys.exc_value).strip('\n\r'))
        if fatal:
            poap_log("ERROR: aborting")
            abort_cleanup_exit()
    if not check_config_size():
        poap_log("ERROR: Loaded config is not big enough, aborting")
        abort_cleanup_exit()


# need to check cnf size as cisco copy default web server html file in case of ret != 200
def check_config_size():
    cnf_size = int(cli("dir %s | head line 1 | sed 's/[A-Z].*//' | sed 's/ //g'" %tmp_dst_cnf).strip('\n'))
    if cnf_size > min_cnf_size:
        return 1
    return 0

def wait_box_online():
    while 1:
        r=int(run_cli("show system internal platform internal info | grep box_online | sed 's/[^0-9]*//g'").strip('\n'))
        if r==1: break
        else: time.sleep(5)
        poap_log("INFO: Waiting for box online...")

def apply_nxos_version():
    wait_box_online()

    try:
        run_cli("config terminal ; boot nxos bootflash:/%s" %(n9k_img_file))
        run_cli("copy running-config startup-config")
        run_cli('copy %s scheduled-config' %tmp_dst_cnf)
    except:
        poap_log("ERROR: setting bootvars or copy run start failed!")
        abort_cleanup_exit()


signal.signal(signal.SIGTERM, sigterm_handler)
poap_log_file = init_poap_log()
if not check_nx_version():
    verify_freespace()
    get_nxos_image()
cdp_switchName, cdp_iftName = get_cdp_inf()
get_sw_config(cdp_switchName, cdp_iftName)
apply_nxos_version()
signal.signal(signal.SIGTERM, sig_handler_no_exit)
poap_log_close()
exit(0)
