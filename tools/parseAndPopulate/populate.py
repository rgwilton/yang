import argparse
import base64
import fnmatch
import json
import os
import subprocess
import sys
import unicodedata
import urllib2


def progress_bar(done, total, time_diff, old_percentage, suffix=''):
    bar_len = 60
    filled_len = int(round(bar_len * done / float(total)))

    percents = round(100.0 * done / float(total), 4)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    time_percentage = percents - old_percentage
    if time_percentage > 0:
        seconds = int((time_diff / time_percentage) * (100 - percents))
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        time_s = "%dh:%02dm:%02ds" % (h, m, s)
    else:
        time_s = "inf"
    sys.stdout.write('[%s] %s%s time remaining %s  ...%s\r' % (bar, percents, '%', time_s, suffix))
    sys.stdout.flush()
    return percents


def find_files(directory, pattern):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                yield filename


# Unicode to string
def unicode_normalize(variable):
    return unicodedata.normalize('NFKD', variable).encode('ascii', 'ignore')


# Make a http request on path with json_data
def http_request(path, method, json_data, credentials):
    try:
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        request = urllib2.Request(path, data=json_data)
        request.add_header('Content-Type', 'application/vnd.yang.data+json')
        request.add_header('Accept', 'application/vnd.yang.data+json')
        base64string = base64.b64encode('%s:%s' % (credentials[0], credentials[1]))
        request.add_header("Authorization", "Basic %s" % base64string)
        request.get_method = lambda: method
        opener.open(request)
    except:
        print 'Could not send request with body ' + json_data + ' and path ' + path
        raise

parser = argparse.ArgumentParser(description="Parse hello messages and yang files to json dictionary. These"
                                             " dictionaries are used for populating a yangcatalog. This script runs"
                                             " first a runCapabilities.py script to create a Json files which are used"
                                             " to populate database.o")
parser.add_argument('--port', default=8008, type=int,
                    help='Set port where the confd is started. Default -> 8008')
parser.add_argument('--ip', default='127.0.0.1', type=str,
                    help='Set ip address where the confd is started. Default -> 127.0.0.1')
parser.add_argument('--credentials', help='Set authorization parameters username password respectively.'
                                          ' Default parameters are admin admin', nargs=2, default=['admin', 'admin']
                    , type=str)
args = parser.parse_args()

prefix = 'http://{}:{}'.format(args.ip, args.port)
subprocess.call('python runCapabilities.py', shell=True)
files = []
# Find all parsed json files
for filename in find_files('./', 'normal*.json'):
    with open(filename) as data_file:
        files.append(json.load(data_file))

vendor = ''
os_from_yang = ''
feature_set = ''
platform = ''
os_version = ''

print("Populating yang catalog with data")

files_prepare = []
for filename_prepare in find_files('./', 'prepare.json'):
    with open(filename_prepare) as data_file:
        print("adding modules")
        read = data_file.read()
        json_modules_data = json.dumps({
            'modules': json.loads(read)
        })

        http_request(prefix + '/api/config/catalog/modules/', 'PATCH',
                     json_modules_data, args.credentials)

# In each json
print("adding vendors")
for data in files:
    # Prepare json_data for put request - this request will prepare list vendors
    # to populate it with protocols and modules
    json_implementations_data = json.dumps(data)
    # Make a PUT request to create a root for each file
    http_request(prefix + '/api/config/catalog/vendors/', 'PATCH', json_implementations_data,
                 args.credentials)

print("Removing temporary json files")

for item in os.listdir('./'):
    if item.endswith(".json"):
        os.remove(item)
