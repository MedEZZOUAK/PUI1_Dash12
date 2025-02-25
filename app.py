import configparser
import logging
import os
import re
from datetime import datetime

from flask import Flask, render_template, jsonify
def load_config():
    config=configparser.ConfigParser()
    config.read('config.ini')
    return config['DEFAULT']
app = Flask(__name__, static_folder='static')
app_config=load_config()


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
        file = open(app_config['LOG_FILE_PATH'], "r", encoding='utf-8')
        try:
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
        finally:
            file.close()
        logs.reverse()
    except FileNotFoundError:
        logging.error("Log file 'log.txt' not found")
    except Exception as e:
        logging.error(f"Error reading log file: {str(e)}")
    return counts, logs, log_data


@app.route('/get-updates')
def get_updates():
    #   init_watcher()
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
    counts, logs, log_data = get_log()
    logging.info(f"Rendering dashboard with {len(logs)} log entries")
    return render_template('dash.html',
                           counts=counts,
                           logs=logs,
                           total_vehicles=log_data.total_vehicles,
                           last_vehicle_time=log_data.last_vehicle_time,
                           current_hour_vehicles=log_data.current_hour_vehicles,
                           current_hour=log_data.current_hour)


if __name__ == '__main__':
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ]
        )
        logging.info("Starting the Dash")
        logging.getLogger('werkzeug').disabled = True
        app.run(debug=False,
                host='0.0.0.0',
                )
    except Exception as e:
        logging.error(f"Application failed to start: {str(e)}")
    finally:
        logging.info("Application shutting down")
