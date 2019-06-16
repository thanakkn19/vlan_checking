# vlan_checking
A small project to automate a task to compare the current VLAN configuration on live switches against the database

Dependencies:
- python2 or python3
- fping
- curl
- python libraries mentioned in requirements.txt

How to:
- Run http server that contains vlan database in the format of json file
- Run the vlan_checking program using the following command:

python3 vlan_compare.py


