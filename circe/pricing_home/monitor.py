#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
    .. note:: This script runs on every node of the system.
"""

__author__ = "Quynh Nguyen, Pradipta Ghosh, Aleksandra Knezevic, Pranav Sakulkar, Jason A Tran and Bhaskar Krishnamachari"
__copyright__ = "Copyright (c) 2018, Autonomous Networks Research Group. All rights reserved."
__license__ = "GPL"
__version__ = "3.0"

import multiprocessing
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import sys
import time
import json
import paramiko
import datetime
from netifaces import AF_INET, AF_INET6, AF_LINK, AF_PACKET, AF_BRIDGE
import netifaces as ni
import platform
from os import path
from socket import gethostbyname, gaierror, error
import multiprocessing
import time
import urllib.request
from urllib import parse
import configparser
from multiprocessing import Process, Manager
from flask import Flask, request
import _thread
import threading
import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler



app = Flask(__name__)

def convert_bytes(num):
    """Convert bytes to Kbit as required by HEFT
    
    Args:
        num (int): The number of bytes
    
    Returns:
        float: file size in Kbits
    """
    return num*0.008

def file_size(file_path):
    """Return the file size in bytes
    
    Args:
        file_path (str): The file path
    
    Returns:
        float: file size in bytes
    """
    if os.path.isfile(file_path):
        file_info = os.stat(file_path)
        return convert_bytes(file_info.st_size)


def receive_price_info():
    """
        Receive price from every computing node, choose the most suitable computing node 
    """
    try:
        pricing_info = request.args.get('pricing_info').split('#')
        print("Received pricing info")
        #Network, CPU, Memory, Queue
        node_name = pricing_info[0]
        price_info = [float(pricing_info[1]),float(pricing_info[2]),float(pricing_info[3]),float(pricing_info[4])]
        task_price_summary[node_name] = price_info
        print(task_price_summary)

    except Exception as e:
        print("Bad reception or failed processing in Flask for pricing announcement: "+ e) 
        return "not ok" 

    return "ok"
app.add_url_rule('/receive_price_info', 'receive_price_info', receive_price_info)    


def default_best_node():
    print('-------- Updating current best node')
    w_net = 1 # Network profiling
    w_cpu = 1 # Resource profiling
    w_mem = 1 # Resource profiling
    w_queue = 1 # Execution time profiling
    cost_list = dict()
    for item in task_price_summary.keys():
        cost_list[item] = task_price_summary[item][0]*w_net +  task_price_summary[item][1]*w_cpu + task_price_summary[item][2]*w_mem + task_price_summary[item][3]*w_queue
    print(cost_list)
    best_node = min(cost_list,key=cost_list.get)
    task_node_summary['current_best_node'] = best_node
    print(task_node_summary)
    print('updated successfully')
    print('update at remote computing nodes')




def update_best_node():
    """Select the best node from price information of all nodes, either default or customized from user price file
    """
    if PRICE_OPTION ==0: #default
        default_best_node()
    else:
        customized_parameters_best_node()
    for computing_ip in all_computing_ips:
        send_controller_info(computing_ip)
    send_controller_info(home_ip)

def schedule_update_price(interval):
    """
        Send controller id node mapping to all the computing nodes
    """
    sched = BackgroundScheduler()
    sched.add_job(update_best_node,'interval',id='push_id', minutes=interval, replace_existing=True)
    sched.start()

def send_controller_info(node_ip):
    retry = 0
    while retry < num_retries:
        try:
            print("Announce my current node mapping to " + node_ip)
            url = "http://" + node_ip + ":" + str(FLASK_SVC) + "/update_controller_map"
            params = {'controller_id_map':controller_id_map}
            print(controller_id_map)
            params = parse.urlencode(params)
            req = urllib.request.Request(url='%s%s%s' % (url, '?', params))
            print(req)
            res = urllib.request.urlopen(req)
            print(res)
            res = res.read()
            res = res.decode('utf-8')
            print(res)
            break
        except Exception as e:
            print("Sending controller message to flask server on computing node FAILED!!!")
            print(e)
            time.sleep(2)
            retry += 1
            return "not ok"

def push_controller_map():
    time.sleep(90)
    for computing_ip in all_computing_ips:
        send_controller_info(computing_ip)
    send_controller_info(home_ip)

def send_assignment_info(node_ip):
    try:
        print("Announce my current best computing node " + node_ip)
        url = "http://" + node_ip + ":" + str(FLASK_SVC) + "/receive_assignment_info"
        assignment_info = self_task+"#"+task_node_summary['current_best_node']
        print(assignment_info)
        params = {'assignment_info': assignment_info}
        params = parse.urlencode(params)
        req = urllib.request.Request(url='%s%s%s' % (url, '?', params))
        res = urllib.request.urlopen(req)
        res = res.read()
        res = res.decode('utf-8')
    except Exception as e:
        print("Sending assignment message to flask server on computing node FAILED!!!")
        print(e)
        return "not ok"

def push_assignment_map():
    time.sleep(120)
    for computing_ip in all_computing_ips:
        send_assignment_info(computing_ip)
    send_assignment_info(home_ip)


def send_monitor_data(msg):
    """
    Sending message to flask server on home

    Args:
        msg (str): the message to be sent

    Returns:
        str: the message if successful, "not ok" otherwise.

    Raises:
        Exception: if sending message to flask server on home is failed
    """
    try:
        print("Sending message", msg)
        url = "http://" + home_node_host_port + "/recv_monitor_data"
        params = {'msg': msg, "work_node": taskname}
        params = parse.urlencode(params)
        req = urllib.request.Request(url='%s%s%s' % (url, '?', params))
        res = urllib.request.urlopen(req)
        res = res.read()
        res = res.decode('utf-8')
    except Exception as e:
        print("Sending message to flask server on home FAILED!!!")
        print(e)
        return "not ok"
    return res

def send_runtime_profile(msg,taskname):
    """
    Sending runtime profiling information to flask server on home

    Args:
        msg (str): the message to be sent

    Returns:
        str: the message if successful, "not ok" otherwise.

    Raises:
        Exception: if sending message to flask server on home is failed
    """
    try:
        print("Sending message", msg)
        url = "http://" + home_node_host_port + "/recv_runtime_profile"
        params = {'msg': msg, "work_node": taskname}
        params = parse.urlencode(params)
        req = urllib.request.Request(url='%s%s%s' % (url, '?', params))
        res = urllib.request.urlopen(req)
        res = res.read()
        res = res.decode('utf-8')
    except Exception as e:
        print("Sending runtime profiling info to flask server on home FAILED!!!")
        print(e)
        return "not ok"
    return res

class MonitorRecv(multiprocessing.Process):
    def __init__(self):
        multiprocessing.Process.__init__(self)

    def run(self):
        """
        Start Flask server
        """
        print("Flask server started")
        app.run(host='0.0.0.0', port=FLASK_DOCKER)



def main():
    """
        -   Load all the Jupiter confuguration
        -   Load DAG information. 
        -   Prepare all of the tasks based on given DAG information. 
        -   Prepare the list of children tasks for every parent task
        -   Generating monitoring process for ``INPUT`` folder.
        -   Generating monitoring process for ``OUTPUT`` folder.
        -   If there are enough input files for the first task on the current node, run the first task. 

    """

    INI_PATH = '/jupiter_config.ini'
    config = configparser.ConfigParser()
    config.read(INI_PATH)

    # Prepare transfer-runtime file:
    global runtime_sender_log, RUNTIME, TRANSFER, transfer_type
    RUNTIME = int(config['CONFIG']['RUNTIME'])
    TRANSFER = int(config['CONFIG']['TRANSFER'])

    if TRANSFER == 0:
        transfer_type = 'scp'

    runtime_sender_log = open(os.path.join(os.path.dirname(__file__), 'runtime_transfer_sender.txt'), "w")
    s = "{:<10} {:<10} {:<10} {:<10} \n".format('Node_name', 'Transfer_Type', 'File_Path', 'Time_stamp')
    runtime_sender_log.write(s)
    runtime_sender_log.close()
    runtime_sender_log = open(os.path.join(os.path.dirname(__file__), 'runtime_transfer_sender.txt'), "a")
    #Node_name, Transfer_Type, Source_path , Time_stamp

    if RUNTIME == 1:
        global runtime_receiver_log
        runtime_receiver_log = open(os.path.join(os.path.dirname(__file__), 'runtime_transfer_receiver.txt'), "w")
        s = "{:<10} {:<10} {:<10} {:<10} \n".format('Node_name', 'Transfer_Type', 'File_path', 'Time_stamp')
        runtime_receiver_log.write(s)
        runtime_receiver_log.close()
        runtime_receiver_log = open(os.path.join(os.path.dirname(__file__), 'runtime_transfer_receiver.txt'), "a")
        #Node_name, Transfer_Type, Source_path , Time_stamp


    # Price calculation methods
    global PRICE_OPTION
    PRICE_OPTION          = int(config['CONFIG']['PRICE_OPTION'])


    global FLASK_SVC, FLASK_DOCKER, MONGO_PORT, username,password,ssh_port, num_retries, task_mul, count_dict,self_ip, home_ip

    FLASK_DOCKER   = int(config['PORT']['FLASK_DOCKER'])
    FLASK_SVC   = int(config['PORT']['FLASK_SVC'])
    MONGO_PORT  = int(config['PORT']['MONGO_DOCKER'])
    username    = config['AUTH']['USERNAME']
    password    = config['AUTH']['PASSWORD']
    ssh_port    = int(config['PORT']['SSH_SVC'])
    num_retries = int(config['OTHER']['SSH_RETRY_NUM'])
    self_ip     = os.environ['OWN_IP']
    home_ip     = os.environ['HOME_NODE']


    global taskmap, taskname, taskmodule, filenames,files_out, home_node_host_port
    global all_nodes, all_nodes_ips, self_id, self_name, self_task
    global all_computing_nodes,all_computing_ips, num_computing_nodes, node_ip_map, controller_id_map

    configs = json.load(open('/centralized_scheduler/config.json'))
    taskmap = configs["taskname_map"][sys.argv[len(sys.argv)-1]]
    # print(taskmap)
    taskname = taskmap[0]
    # print(taskname)
    if taskmap[1] == True:
        taskmodule = __import__(taskname)

    #target port for SSHing into a container
    filenames=[]
    files_out=[]
    self_name= os.environ['NODE_NAME']
    self_id  = os.environ['NODE_ID']
    self_task= os.environ['TASK']
    controller_id_map = self_task + ":" + self_id
    #update_interval = 10 #minutes
    home_node_host_port =  home_ip + ":" + str(FLASK_SVC)

    all_computing_nodes = os.environ["ALL_COMPUTING_NODES"].split(":")
    all_computing_ips = os.environ["ALL_COMPUTING_IPS"].split(":")
    num_computing_nodes = len(all_computing_nodes)
    node_ip_map = dict(zip(all_computing_nodes, all_computing_ips))

    update_interval = 3 

    global dest_node_host_port_list
    dest_node_host_port_list = [ip + ":" + str(FLASK_SVC) for ip in all_computing_ips]

    global task_price_summary, task_node_summary
    manager = Manager()
    task_price_summary = manager.dict()
    task_node_summary = manager.dict()

    # Set up default value for task_node_summary: the task controller will perform the tasks also
    task_node_summary['current_best_node'] = self_id

    _thread.start_new_thread(push_controller_map,())
    _thread.start_new_thread(schedule_update_price,(update_interval,))
    _thread.start_new_thread(push_assignment_map,())

    web_server = MonitorRecv()
    web_server.run()
    #web_server.start()

    if taskmap[1] == True:
        task_mul = manager.dict()
        count_dict = manager.dict()
        

        # #monitor INPUT as another process
        # w=Watcher()
        # w.run()

    else:

        path_src = "/centralized_scheduler/" + taskname
        args = ' '.join(str(x) for x in taskmap[2:])

        if os.path.isfile(path_src + ".py"):
            cmd = "python3 -u " + path_src + ".py " + args          
        else:
            cmd = "sh " + path_src + ".sh " + args
        os.system(cmd)

if __name__ == '__main__':
    main()
    
