#!/usr/bin/env python

#Use ssh/cli to extract info regarding vlan
#Alternatively, NETCONF or RESTCONF could work as well,
#as long as the switch allows them

import paramiko
from account import account
import subprocess

def get_ip():
	result = subprocess.run(['ifconfig', 'eth0'])
	print(type(result))
	ip_index_bg = result.find('addr') + 5
	ip_len = result[ip_index_bg:].find(' ')
	myip = result[ip_index_bg:ip_index_bg + ip_len]
	print("My ip is {}".format(myip))

	subnet = '.'.join(myip.split('.')[0:3] + [0])
	IPs = subprocess.run(['fping', '-aqg', str(subnet)], stdout=subprocess.PIPE)
	return IPs

def connect_ssh(ip):
	client = SSHClient()
	client.set_missing_host_key_policy(AutoAddPolicy)
	try:
		client.connect(ip, username=account['username'],
				passowrd=account['password'])
		stdin, stdout, stderr = client.exec_command('show ip int br')
		print(stdin, stdout, sterr)
	except AuthenticationException:
		print("The connection to {} can not be authenticated, skipping ...".format(ip))
	except:
		print("SSH connection to {} fails, skipping ...".format(ip))
		

def get_vlan_from_ssh():
	pass

def extract_vlan():
	pass

def get_vlan_from_http():
	pass

def main():
	pass

if __name__ == '__main__':
	#Get IP data from a text file
	IPs = get_ip()
	for ip in IPs:
		print("Current IP is {}".format(ip))
		#connect_ssh(ip)
