#!/usr/bin/env python

#Use ssh/cli to extract info regarding vlan
#Alternatively, NETCONF or RESTCONF could work as well,
#as long as the switch allows them

import paramiko
import subprocess
import time
import json
import sys
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
	active_IPs = IPs.stdout.decode('utf8').strip().split()
	return active_IPs

def ssh_get_vlan(text):
	"""
	This function extract vlan id for each type of vlan from the input

	Input : str

	Example Input :
	term len 0
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
		if len(columns) < 3 or "active" != columns[2] or  columns[0] in {'1', '1001', '1002', '1003', '1004', '1005'}:
			continue
		vlan_dict[columns[1]] = columns[0]
	return vlan_dict

def print_vlan(vlan_dict):
	print("Printing output in print_vlan function ...")
	print("------------------------------------------")
	for item in vlan_dict.items():
		print("VLAN ID for %s VLAN is %s" % (item[1], item[0]))

def http_get_vlan(IPs):
	"""
	This function tries to get vlan database in json format from a given list of potentail http server
	Input: server_ip (str)
	Output:
	- None, if server_ip is not an actual http server
	[TODO] : create a DNS map to automatically detect the http server address to eliminate the need to run this in a loop
	- dict() containing the vlan database in json format
	Output Example:
	{
		"accsw": {
			"R1": {
				"vlan-profile": "home-1",
				"override": {
					"infra": 102
				}
			}
		},
		"vlan-profiles": {
			"home-1": {
				"infra": 100,
				"runt": 200,
				"engineer": 300
			}
		}
	}

	"""
	#server_ip = "192.168.204.162"
	port = "8000"
	for server_ip in IPs:
		url = "http://" + server_ip + ":" + port + "/" + "port_info.json"
		try:
			proc = subprocess.Popen(["curl", "-s", url], stdout=subprocess.PIPE)
			(output_in_bytes,err) = proc.communicate()
			http_response = output_in_bytes.decode('utf8')
			json_response = json.loads(http_response)
			print("Parsing json data successful!!")
			return json_response
		except:
			print("\nPort {} on {} is not opened, skipping this address ... \n".format(port, server_ip))

def connect_ssh(ip):
	"""
	Receive IP address in string, try to log in to  such device using ssh,
	and then execute a command to capture all the VLANs defined on the device

	Input: ip (str)
	Output: the result of show vlan brienf | include active (str)

	Example: [TODO]
	"""
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

def get_hostname(text):
	"""
	Parse a hostname from the string containing vlan data

	Input: text (str)
	Example:
	R1>show switch-vlan brief | inc active

	Output: hostname (str)
	"""
	return text[text.find('\n')+1:text.find('>')]

def adjust_vlan_database(json_dict, device):
	"""
	Adjust vlan from dictionary for each switch according to the vlan profile and return vlan dict

	Input: json_dict (dict)
	{
		"accsw":{
			"R1": {
				"vlan_profile": "profile_name",
				"override": {
					"vlan_name": vlan_id
				}
			}
		},
		"vlan_profile":{
			"profile_name_1": {
				"infra": vlan_id,
				"engineer": vlan_id
			}
		}
	}

	Output: vlan_dict (dict)
	key(str): value(int)
	{
		"vlan_name": vlan_id,
		"vlan_name": vlan_id
	}
	"""
	get_device = json_dict.get("accsw").get(device)
	profile = get_device.get("vlan-profile")
	override = get_device.get("override", None)
	get_profile = json_dict.get("vlan-profiles").get(profile)
	if not override:
		return get_profile
	for item in override.items():
		get_profile[item[0]] = item[1]
	return get_profile


if __name__ == '__main__':
	#Get IP data from a text file, search from all the alive devices which one allow SSH connections
	active_IPs = get_ip()

	#Gathering VLAN dictionaries for each live network device
	vlan_dict_ssh = {}

	for ip in active_IPs:
		raw_output = connect_ssh(ip)
		if raw_output:
			hostname = get_hostname(raw_output[:20])
			print("hostname is %s" % hostname)
			vlan_dict_ssh[hostname] = ssh_get_vlan(raw_output)
			#print_vlan(ssh_get_vlanh(raw_output))
	#for item in vlan_dict_ssh.items():
	#	print(item[0], item[1])

	vlan_database = http_get_vlan(active_IPs)

	#Get a list of all devices in our database
	device_list = list(vlan_database.get("accsw").keys())
	for device_name in device_list:
		device_vlans = adjust_vlan_database(vlan_database, device_name)
		print("VLAN Database for %s is " %device_name)
		print(device_vlans)
		print("VLAN from the live configs are :")
		print(vlan_dict_ssh[device_name])

