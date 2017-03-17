#coding:utf-8

'''
@author: shuai.chen
Created on 2017年3月4日
'''
from __future__ import absolute_import

import re
import logging
from thrift import TMultiplexedProcessor

from .factory import ThriftProcessPoolServer
from wrpc.manager.register import Register
from wrpc.common import constant, util

logger = logging.getLogger(__name__)

class Server(object):
    """server class"""
    
    def __init__(self, zk_client, server_config, server_class=ThriftProcessPoolServer, **kwargs):
        """
        create server instance
        @param zkclient: zookeeper connection client
        @param server_config: instance of ServerConfig class
        @param server_class: child class of ServerFactory, default is ThriftProcessPoolServer
        @param kwargs: 
            process_num: process num
            coroutines_num: gevent coroutines num
        """
        self.__zk_client = zk_client
        self.__server_config = server_config
        self.__kwargs = kwargs
        
        self.__register = Register(zk_client)
        self.__set_server(server_class)

    def __set_server(self, server_class):
        mprocessor = self.__get_processor()
        ip, port = self.__server_config.get_server_ip(), self.__server_config.get_port()
        self.__server = server_class(mprocessor, ip, port, **self.__kwargs)   
    
    def __get_processor(self):
        mprocessor = TMultiplexedProcessor.TMultiplexedProcessor()
        for handler in self.__server_config.get_handlers():
            split = self.get_module_string(handler.__bases__[0]).split(".")
            name = split[-2]
            module = __import__(".".join(split[:-1]), globals={}, locals={}, fromlist=[name])
            processor = getattr(module, "Processor")
            mprocessor.registerProcessor(name, processor(handler()))
        return mprocessor    
    
    @staticmethod
    def get_module_string(module):   
        module_string = str(module)
        if "'" in module_string:
            pat = "(?<=\\').+?(?=\\')"
            search = re.search(pat, module_string)
            if search:
                return search.group(0)
        return module_string
    
    def register_server(self):
        self.__register.register_and_listen(self.__server_config)
     
    def start(self):
        logger.info("start server.")
        self.register_server()
        if self.__server:
            self.__server.start() 
            
    def stop(self):
        if self.__server:
            self.__server.stop()
        if self.__zk_client:
            self.__zk_client.close()    
            
class ServerConfig(object):
    
    def __init__(self,global_service, handlers,
                 port=constant.PORT_DEFAULT, version=constant.VERSION_DEFAULT,
                 weight=constant.WEIGHT_DEFAULT, ip=None):   
        """
        server config
        @param global_service: global service name
        @param handlers: handlers implemented ifaces
        @param port: server port default is 9090
        @param version: server version default is 1.0.0
        @param weight: server weight default is 1
        @param ip: ip address if you force config it instead of getting local ip 
        """  
        self.__global_service = global_service
        self.__handlers = handlers
        self.__port = port
        self.__version = version
        self.__weight = weight
        
        self.__ip = ip
        self.set_local_ip()
        
    def get_port(self):
        return self.__port    
    
    def get_handlers(self):
        return self.__handlers
    
    def get_ip(self):
        return self.__ip
    
    def get_server_ip(self):
        return self.__ip or self.__local_ip
    
    def set_local_ip(self):
        self.__local_ip = util.get_local_ip()
        
    def get_path(self):
        return "{0}{1}{2}{3}{4}{5}".format(                                    
                                    constant.ZK_SEPARATOR_DEFAULT,
                                    self.__global_service,
                                    constant.ZK_SEPARATOR_DEFAULT,
                                    self.__version ,
                                    constant.ZK_SEPARATOR_DEFAULT,
                                    self.get_node_name()                                         
                                    )    
        
    def get_node_name(self):
        return "{0}:{1}:{2}".format(
                                     self.get_server_ip(),
                                     self.__port,
                                     self.__weight
                                     ) 