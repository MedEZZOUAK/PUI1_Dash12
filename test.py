import random
import time
from datetime import datetime

log_file = 'log.txt'

def generate_log_entry():
    log_types = ['INFO', 'ERROR', 'FATAL']
    log_type = random.choice(log_types)
    timestamp = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    if log_type == 'INFO':
        message = f'Nombre de vehicules = {random.randint(1, 5)} (SSYNC.Modules.Transformation.ThreadTransformation - l.1084)'
    else:
        message = f'Some {log_type.lower()} message'
    return f'{timestamp} {log_type} {message}\n'

def append_log_entry():
    with open(log_file, 'a', encoding='utf-8') as file:
        message = generate_log_entry()
        print(message)
        file.write(message)

if __name__ == '__main__':
    while True:
        append_log_entry()
        time.sleep(random.randint(1, 5))