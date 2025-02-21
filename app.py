import logging
import os
import re
from datetime import datetime
from queue import Queue

from flask import Flask, render_template, jsonify, Response
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

app = Flask(__name__, static_folder='static')


class LogData:
    """
    Model for the logs :
    total_vehicles : The numbre of cars in the whole log file aka the number of cars produced that day
    last_vehicle_time : The time stamp of the last vehicule produced (Nombre de vehicules != 0)
    current_hour_vehicles : The number of cars produced in this current hour
    current_hour : the current hour being tracked
    """

    def __init__(self):
        self.total_vehicles = 0
        self.last_vehicle_time = None
        self.current_hour_vehicles = 0
        self.current_hour = None


def parse_vehicle_count(message):
    """
    :param message:
    :return: Nomber of cars in that message
    eg : logger: Nombre de vehicules = 1 (SSYNC.Modules.Transformaton.ThreadTransformation - l.1084)
    the function return 1
    """
    match = re.search(r'Nombre de vehicules = (\d+)', message)
    return int(match.group(1)) if match else 0.


def init_watcher():
    """
    init the file_oserver and the event_handler the two global var if not already initialized
    """
    global file_observer, event_handler
    if file_observer is None:
        logging.info("Initializing file watcher")
        file_observer, event_handler = setup_file_watcher()


def get_log():
    """
    Using a regex expression to detect INFO, FATAL, and ERROR type of logs from the whole file.
    Counts the occurrence of each type and extracts log details (timestamp, type, and message).
    And indentify the Info log (the one that have the cars info ), sum the number of cars in totals , and for the current hour ,last vehicle production timestamp,
    and the hour being tracked
    :return :
    counts : the number of each log
    logs : logs that will be displayed (a list )
    log_data : entity with the summarized logs data
    """
    pattern = r'(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+(INFO|FATAL|ERROR)'
    counts = {'INFO': 0, 'FATAL': 0, 'ERROR': 0}
    logs = []
    log_data = LogData()
    try:
        with open("log.txt", "r", encoding='utf-8') as file:
            for line in file:
                match = re.match(pattern, line)
                if match:
                    timestamp = match.group(1)
                    log_type = match.group(2)
                    message = line[match.end():].strip()
                    current_time = datetime.strptime(timestamp, '%Y/%m/%d %H:%M:%S')

                    if log_type == "INFO" and "Nombre de vehicules =" in message:
                        vehicle_count = parse_vehicle_count(message)
                        if vehicle_count > 0:
                            log_data.total_vehicles += vehicle_count
                            log_data.last_vehicle_time = current_time
                            now = datetime.now()
                            current_hour = now.replace(minute=0, second=0, microsecond=0)

                            if log_data.current_hour != current_hour:
                                log_data.current_hour = current_hour
                                log_data.current_hour_vehicles = vehicle_count if current_time.hour == now.hour else 0
                            else:
                                if current_time.hour == now.hour:
                                    log_data.current_hour_vehicles += vehicle_count
                        counts[log_type] += 1
                        logs.append({
                            'timestamp': timestamp,
                            'type': log_type,
                            'message': message,
                            'hour': current_time.strftime('%Y-%m-%d %H:00'),
                            'vehicle_count': vehicle_count
                        })
                    elif log_type in ["ERROR", "FATAL"]:
                        counts[log_type] += 1
                        logs.append({
                            'timestamp': timestamp,
                            'type': log_type,
                            'message': message
                        })
        logs.reverse()
    except FileNotFoundError:
        logging.error("Log file 'log.txt' not found")
    except Exception as e:
        logging.error(f"Error reading log file: {str(e)}")
    return counts, logs, log_data


class MyHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.clients = set()

    def on_modified(self, event):
        if event.src_path.endswith('log.txt'):
            for client in list(self.clients):
                try:
                    client.put("update")
                except Exception as e:
                    logging.error(f"Error notifying client: {str(e)}")
                    self.clients.remove(client)


def setup_file_watcher():
    observer = Observer()
    event_handler = MyHandler()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    return observer, event_handler


file_observer = None
event_handler = None


@app.route('/stream')
def stream():
    init_watcher()

    def event_stream():
        queue = Queue()
        event_handler.clients.add(queue)
        try:
            while True:
                message = queue.get()
                yield f"data: {message}\n\n"
        finally:
            event_handler.clients.remove(queue)

    return Response(event_stream(), mimetype="text/event-stream")


@app.route('/get-updates')
def get_updates():
    init_watcher()
    counts, logs, log_data = get_log()
    return jsonify({
        'counts': counts,
        'logs': logs,
        'total_vehicles': log_data.total_vehicles,
        'last_vehicle_time': log_data.last_vehicle_time.strftime(
            '%Y/%m/%d %H:%M:%S') if log_data.last_vehicle_time else None,
        'current_hour_vehicles': log_data.current_hour_vehicles,
        'current_hour': log_data.current_hour.strftime('%Y-%m-%d %H:00') if log_data.current_hour else None
    })


@app.route('/')
def dashboard():
    global file_observer, event_handler
    if file_observer is None:
        file_observer, event_handler = setup_file_watcher()
    counts, logs, log_data = get_log()
    return render_template('dash.html',
                           counts=counts,
                           logs=logs,
                           total_vehicles=log_data.total_vehicles,
                           last_vehicle_time=log_data.last_vehicle_time,
                           current_hour_vehicles=log_data.current_hour_vehicles,
                           current_hour=log_data.current_hour)


if __name__ == '__main__':
    try:
        init_watcher()
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(LOG_DIR, 'app.log')),
                logging.StreamHandler()
            ]
        )
        app.run(debug=True,
                host='0.0.0.0'
                )
    finally:
        if file_observer:
            file_observer.stop()
            file_observer.join()
