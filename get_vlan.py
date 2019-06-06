#!/usr/bin/env python

#Use ssh/cli to extract info regarding vlan
#Alternatively, NETCONF or RESTCONF could work as well,
#as long as the switch allows them

import paramiko
import subprocess
import time
from account import account
from functools import reduce

def mask_to_slash(mask):
	mask_val= reduce(lambda x,y: (x<<8) + y, [int(m) for m in mask.split('.')])
	mask_bits = 0
	while (1<<31)&mask_val:
		mask_bits += 1
		mask_val <<= 1
	return mask_bits

def get_pattern(pattern, string, trailing_pattern):
	pos = string.find(pattern) + len(pattern)
	length = string[pos:].find(trailing_pattern)
	return string[pos:pos+length]

def get_ip():
	#"""
	#This function extracts the local IP and sub network
	#from "ifconfig", and then return a list of live IP addresses
	#in the subnet
	#Output : list of IP addresses as strings
	#"""
	result = subprocess.run(['ifconfig', 'eth0'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
	myip = get_pattern("inet addr:", result.stdout, ' ')
	print("\nMy ip is {}".format(myip))

	mask = get_pattern("Mask:", result.stdout, '\n')
	subnet = '.'.join(myip.split('.')[0:3] + ['0']) + "/" + str(mask_to_slash(mask))
	print("Scanning subnet : %s" % subnet)

	IPs = subprocess.run(['fping', '-aqg', subnet], stdout=subprocess.PIPE)
	IPs_out = IPs.stdout.decode('utf8').strip().split()
	return IPs_out

def get_vlan_from_ssh(text):
	"""
	This function extract vlan id for each type of vlan from the input

	Input : str

	Example Input :
	ESW1>show vlan-switch brief | inc active
	1    default                          active    Fa1/0, Fa1/1, Fa1/2, Fa1/3
	100  runt                             active
	200  infra                            active
	300  engineer                         active
	1002 fddi-default                     active
	1003 token-ring-default               active
	1004 fddinet-default                  active
	1005 trnet-default                    active

	Output : dictionary with key:value pair as vlan_name:vlan_id
	"""

	vlan_dict = {}
	for line in text.split('\n'):
		#Needs to skip all lines till first line of VLAN shows
		columns = line.split()
		#print(columns)
		if len(columns) < 3 or "active" not in columns[2]:
			continue
		if columns[0] in {'1', '1001', '1002', '1003', '1004', '1005'}:
			continue
		vlan_dict[columns[1]] = columns[0]
	return vlan_dict

def print_vlan(vlan_dict):
	print("Printing output in print_vlan function ...")
	print("------------------------------------------")
	for item in vlan_dict.items():
		print("VLAN ID for %s VLAN is %s" % (item[1], item[0]))


def connect_ssh(ip):
	client = paramiko.client.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy)
	try:
		print("Connecting to %s" % ip)
		client.connect(ip, username='thanakorn', password='cisco')
		cmd_str = 'show vlan-switch brief | inc active'
		print("\nConnection to %s has been established. Executing %s ..." % (ip, cmd_str))
		client_shell = client.invoke_shell()
		out = client_shell.recv(1000)
		client_shell.send('term len 0\n')
		client_shell.send(cmd_str + '\n')
		time.sleep(2)
		out = client_shell.recv(5000)
		hr_out = out.decode('utf8')
		print(hr_out)
		print("Connection is being terminated.")
		client.close()
		return hr_out

	except paramiko.ssh_exception.AuthenticationException:
		print("The connection to {} can not be authenticated, skipping ...".format(ip))

	except paramiko.ssh_exception.BadHostKeyException:
		print("The connection to {} has bad host key, skipping ...".format(ip))

	except paramiko.ssh_exception.SSHException :
		print("The connection to {} has an SSH Exceltin, skipping ...".format(ip))

	except:
		print("SSH connection to {} fails due to socket error, skipping ...".format(ip))

def get_vlan_from_http():
	pass

def main():
	pass

if __name__ == '__main__':
	#Get IP data from a text file
	IPs = get_ip()
	for ip in IPs:
		raw_output = connect_ssh(ip)
		if raw_output:
			#vlan_dict = get_vlan_from_ssh(raw_output)
			print_vlan(get_vlan_from_ssh(raw_output))
