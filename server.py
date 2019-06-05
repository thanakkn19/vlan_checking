#!/usr/bin/env python

"""
This is a server hosting vlan database and will respond to an http request message and reply with vlan_name:vlan_id pair
"""

import socket

def run_server():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port,max_session_num =  1234, 4
        s.bind(('', port))
        print("Socket binded to port {}".format(port))

        s.listen(max_session_num)
        print("Socket is in listening mode ...")

        #Server is now listening to all incoming connection
        while True:
                c, addr = s.accept()
                print("Receive a connection from {}".format(addr))
                c.send("Hello, nice to meet you!!".encode())
                c.send("Terminating the child socket...".encode())
                c.close()

if __name__ == "__main__":
        run_server()


