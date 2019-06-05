#!/usr/bin/env python

import socket
import sys
import os

def client_run(ip):
	c = socket.socket()
	port, server_ip = 1234, ip
	c.connect((server_ip, port))
	print(c.recv(1024).decode('utf8'))
	c.close

def pingable(IP):
	response = os.system("ping -c 1 " + IP + " > /dev/null ")
	if response == 0:
		return True
	return False

if __name__ == '__main__':
	if len(sys.argv) < 2:
		print("Usage: python3 client <IP_address_of_server>")
		sys.exit(2)
	server_ip = sys.argv[1]
	if not pingable(server_ip):
		print("IP {} is not pingable!".format(server_ip))
		sys.exit(1)
	client_run(server_ip)
