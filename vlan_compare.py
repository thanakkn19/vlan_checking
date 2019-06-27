#!/usr/bin/env python

#Use ssh/cli to extract info regarding vlan
#Alternatively, NETCONF or RESTCONF could work as well,
#as long as the switch allows them

import paramiko
import subprocess
import time
import json
import sys, os
import getopt
import requests
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
	""" 
	This function extracts the local IP and sub network
	from "ifconfig", and then return a list of live IP addresses
	in the subnet
	It is only used when this program is called without a devicefile option
	Output : list of IP addresses as strings
	"""
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
		if len(columns) < 3 or "active" != columns[2] or  columns[0] in {'1', '1001', '1002', '1003', '1004', '1005'}:
			continue
		vlan_dict[columns[1]] = int(columns[0])
	return vlan_dict

def print_vlan(vlan_dict):
	print("Printing output in print_vlan function ...")
	print("------------------------------------------")
	for item in vlan_dict.items():
		print("VLAN ID for %s VLAN is %s" % (item[1], item[0]))

def http_get_vlan(IPs, server_ip="192.168.1.3"):
	""" 
	This function tries to get vlan database in json format from a given list of potentail http server
	Input: server_ip (str)
	Output:
	- None, if server_ip is not an actual http server
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
	port = "8000"
	url = "http://" + server_ip + ":" + port + "/" + "port_info.json"
	try:
		response = requests.get(url)
		if response.status_code == 200:
			output = response.json()
			return output
		print("Request failed. Error code: ",response.status_code)
	except:
		print("\nPort {} on {} is not opened, skipping this address ... \n".format(port, server_ip))

	""" 
	response = subprocess.Popen(["curl", "-s", url], stdout=subprocess.PIPE)
	returncode = response.returncode
	(output_in_bytes,err) = proc.communicate()
	http_response = output_in_bytes.decode('utf8')
	json_response = json.loads(http_response)
	print("Parsing json data successful!!")
	return json_response
 	"""

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
		print("Connection is being terminated.\n")
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
				"vlan-profile": "profile_name",
				"override": {
					"vlan_name": vlan_id
				}
			}
		},
		"vlan-profiles":{
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
	get_device_dict = json_dict.get("accsw").get(device)
	profile = get_device_dict.get("vlan-profile", None)
	override = get_device_dict.get("override", None)
	get_profile = json_dict.get("vlan-profiles").get(profile)
	if not override:
		return get_profile
	c_get_profile = get_profile.copy()
	for vlan, vlan_id in override.items():
		c_get_profile[vlan] = vlan_id
	return c_get_profile

def usage(type=0):
	if type == 1:
		print("\nInvalid option!")
	print("\nUsage: python vlan_compare.py or python vlan_compare.py -f <devicefile>\n")

def main(argv):

	devices = []
	if len(argv) == 0:
		#Get IP data from a text file, search from all the alive devices which one allow SSH connections
		devices = get_ip()
	else:
		devicefile = ''
		try:
			opts, args = getopt.getopt(argv, "f:",["file="])
		except getopt.GetoptError:
			usage()
			sys.exit(2)
		for opt, arg in opts:
			if opt in ('-f', '--file'):
				devicefile = arg
			else:
				usage(1)
				sys.exit(2)
		if not os.path.isfile(devicefile):
			print("\n{} is not a valid filename in the current working directory.\n".format(devicefile))
			sys.exit()
		with open(devicefile, 'r') as file:
			devices = [x.strip('\n') for x in file.readlines() if x != '\n']


	#Gathering VLAN dictionaries for each live network device
	vlan_config_dict = {}

	for ip in devices:
		raw_output = connect_ssh(ip)
		if raw_output:
			hostname = get_hostname(raw_output[:20])
			vlan_config_dict[hostname] = ssh_get_vlan(raw_output)

	vlan_database_dict = http_get_vlan(devices)

	#Get a list of all devices in our database
	device_list = list(vlan_database_dict.get("accsw").keys())
	for device_name in device_list:
		device_vlans_dict = adjust_vlan_database(vlan_database_dict, device_name)

		#Need to look for matching VLANs
		vlan_list = list(device_vlans_dict.keys())
		for vlan_name in vlan_list:
			vlan_id_from_config_dict = vlan_config_dict[device_name].get(vlan_name, None)

			#If the VLAN exists on the device and the database
			if vlan_id_from_config_dict:
				device_vlan = device_vlans_dict.get(vlan_name, None)
				#If VLAN IDs dont' match
				if vlan_id_from_config_dict != device_vlan:
					print("%s --- VLAN Mismatched: %s VLAN is configured as %d on %s, but it is %d on port_info.json" % (device_name, vlan_name, vlan_id_from_config_dict, device_name, device_vlan))
			else:

				#If the VLAN only exists on the database but not on the device
				print("%s --- VLAN Missing: %s VLAN is not configured on the device" % (device_name, vlan_name))

		#If there's any VLANs configured on the switch that are not in the database
		extra_vlans = set(vlan_config_dict[device_name]) - set(vlan_list)
		if extra_vlans != set():
			print("%s --- Unauthorized VLAN exists: The following VLAN(s) exist but are not defined on the database. Please remove them or update the database!!!" % device_name)
			for vlan_name in extra_vlans:
				print("       - %s : %d" %(vlan_name, vlan_config_dict.get(device_name).get(vlan_name)))
		print("\n")

if __name__ == "__main__":
	main(sys.argv[1:])
