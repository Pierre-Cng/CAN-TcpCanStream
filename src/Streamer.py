import zmq
import time 
import socket
import threading 
from queue import Queue 
import can
import cantools 
import pandas as pd 
import json 
from datetime import datetime
import pysftp
import os

class Streamer:
    def __init__(self):
        self.dbc = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'battery.dbc')
        self.router_ip = '192.168.137.1' # dummy values 
        self.port_pubsub = '5558' # dummy values 
        self.port_routerdealer = '5559' # dummy values 
        self.timeout = 100
        self.data_queue = Queue()
        self.stop_event = threading.Event()
        self.configure_socket()

    def configure_socket(self):
        context = zmq.Context()
        self.sub_socket = context.socket(zmq.SUB)
        try:
            self.sub_socket.connect(f'tcp://{self.router_ip}:{self.port_pubsub}')
        except Exception as e:
            print(f'Error connecting to socket: {e}')
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    def identify_response(self, router_ip, port):
        context = zmq.Context()
        dealer_socket = context.socket(zmq.DEALER)
        dealer_socket.connect(f'tcp://{router_ip}:{port}')
        message_id = str(-1)
        message = socket.gethostname()
        for attempt in range(5):
            try:
                dealer_socket.send_multipart([message_id.encode(), message.encode()])
                time.sleep(0.05)
            except Exception as e:
                print(f'Error sending message: {e}')
        dealer_socket.close()
        context.term()

    def send_data(self, router_ip, port, data_queue, stop_event):
        print('start send data')
        context = zmq.Context()
        dealer_socket = context.socket(zmq.DEALER)
        dealer_socket.connect(f'tcp://{router_ip}:{port}')
        message_id = 0 
        while not stop_event.is_set():
            if not data_queue.empty():
                data_line = data_queue.get()
                for attempt in range(2):
                    try:
                        id = str(message_id)
                        dealer_socket.send_multipart([id.encode(), data_line.encode()])
                        time.sleep(0.005)
                        print(id, data_line)
                    except Exception as e:
                        print(f'Error sending message: {e}')
                message_id += 1
        dealer_socket.close()
        context.term()

    def canbus_reader(self, dbc, data_queue, stop_event):
            print('start can reader')
            bus = can.interface.Bus(channel='can0', bustype='socketcan')
            decoder = Decoder(dbc)
            try:
                start_time = time.perf_counter()
                while not stop_event.is_set():
                    message = bus.recv(timeout=0.1)  
                    if message is not None:
                        timestamp = start_time - time.perf_counter()
                        decoder.add_msg(timestamp, message.arbitration_id, message.data, data_queue)
            except Exception as e:
                print(f'Error decoding message: {e}')
            finally:
                bus.shutdown()
                decoder.data.convert_to_csv()
                decoder.data.convert_to_json()

    def thread_function(self, target, args): 
        data_flow_thread = threading.Thread(target=target, args=args)
        data_flow_thread.daemon = True 
        data_flow_thread.start()
        return data_flow_thread

    def sftp_upload_folder(self, local_folder_path, remote_folder_path, hostname, username, password):
        with pysftp.Connection(host=hostname, username=username, password=password) as sftp:
            sftp.chdir(remote_folder_path)
            sftp.put_r(local_folder_path)

    def switch_command(self):
        while True:
            try:
                topic, message = self.sub_socket.recv_multipart(flags=zmq.DONTWAIT)
                print(topic, message)
            except zmq.Again:
                topic = b''
            if topic.decode() == 'identify':
                self.thread_function(self.identify_response, (self.router_ip, self.port_routerdealer))
            if topic.decode() == 'start':
                print('start recording')
                self.stop_event.clear()
                self.thread_function(self.canbus_reader, (self.dbc, self.data_queue, self.stop_event))
                self.thread_function(self.send_data, (self.router_ip, self.port_routerdealer, self.data_queue, self.stop_event))
            if topic.decode() == 'stop':
                self.stop_event.set()
                #self.sftp_upload_folder('./', './', self.router_ip, user, passwd)

class Decoder:
    def __init__(self, dbc):
        self.dbase = cantools.database.load_file(dbc)
        self.data = Data()

    def add_msg(self, timestamp, frame_id, data, data_queue):
        try:
            self.data.log_to_file('raw_trace', f'{timestamp}, {frame_id}, {data}')
            message = self.dbase.get_message_by_frame_id(frame_id)
            decoded_signals = message.decode(data, allow_truncated=True)            
        except Exception as e:
                print(f'Failed to parse data of frame: Id {frame_id}, Timestamp: {timestamp}, Raw data: {data}')
                print(f'(0x{frame_id:x}): {e}')

        for signal in decoded_signals:
            x = timestamp
            y = decoded_signals[signal]
            if isinstance(y, cantools.database.namedsignalvalue.NamedSignalValue):
                y = y.value
            signal = message.name + '.' + signal
            data_queue.put(f'{signal}, {x}, {y}')
            self.data.add_value(signal, x, y)

class Data:
    def __init__(self):
        self.signals = {}
        self.current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.hostname = socket.gethostname()

    def add_value(self, signal, x, y):
        self.log_to_file('decoded_trace', f'{signal}, {x}, {y}')
        if signal not in self.signals:
            self.signals[signal] = {'name': signal, 'x':[], 'y':[]}
        self.signals[signal]['x'].append(x)
        self.signals[signal]['y'].append(y)
    
    def log_to_file(self, logtype, string):
        with open(f'{self.hostname}__{logtype}_can__{self.current_datetime}.txt', 'a') as file:
            file.write(string + '\n')

    def dict_obj_converter(self, obj):
        return obj.__dict__
    
    def convert_to_csv(self):
        master_df = pd.DataFrame(columns=['Signal', 'x', 'y'])  
        for signal in self.signals:
            x_values = self.signals[signal]['x']
            y_values = self.signals[signal]['y']
            master_df = master_df._append({'Signal': signal, 'x': x_values, 'y': y_values}, ignore_index=True)
        master_df.to_csv(f'{self.hostname}__decoded_data__{self.current_datetime}.csv', index=False)
    
    def convert_to_json(self):
        with open(f'{self.hostname}__decoded_data__{self.current_datetime}.json', 'w') as json_file:
            json.dump(self.signals, json_file, default=self.dict_obj_converter, indent=4)

def main():
    streamer = Streamer()
    streamer.switch_command()
    
if __name__=='__main__':
    main()
