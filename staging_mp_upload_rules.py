import csv
import json
import sys
import requests
import dns.resolver
import threading
import queue

# Check if file exists

if len(sys.argv) < 2:
    print('No file provided, no rules to upload')
    sys.exit()
else:
    file_name = sys.argv[1]


tasks_queue = queue.Queue()


def _get_canonical_name(hostname_www):
    print('Attempting to get canonical name for %s' % hostname_www)
    resolver = dns.resolver.Resolver()
    try:
        canonical_name = resolver.resolve(hostname_www).canonical_name.to_unicode().rstrip('.')
    except dns.resolver.NXDOMAIN:
        print('Nonexistent domain %s' % hostname_www)
        return None
    if canonical_name != hostname_www:
        print('%s has canonical name %s' % (hostname_www, canonical_name))
    return canonical_name


# Replace 'paulm-sony.test.edgekey.net' with the actual hostname
get_canonical_name = _get_canonical_name('www.playstation.com')

if get_canonical_name:
    staging_host = get_canonical_name.replace('akamaiedge', 'akamaiedge-staging')
else:
    sys.exit('Failed to get canonical name')


def resolveDNSA():
    domain = staging_host
    resolver = dns.resolver.Resolver()
    answer = resolver.resolve(domain, "A")
    return answer


resultDNSA = resolveDNSA()
resultant_str = ''.join(str(item) for item in resultDNSA)

print(resultant_str)


class HostHeaderSSLAdapter(requests.adapters.HTTPAdapter):
    def resolve(self, hostname):
        ips = resultant_str
        resolutions = {'paulm-sony.test.edgekey.net': ips}
        return resolutions.get(hostname)

    def send(self, request, **kwargs):
        from urllib.parse import urlparse

        connection_pool_kwargs = self.poolmanager.connection_pool_kw

        result = urlparse(request.url)
        resolved_ip = self.resolve(result.hostname)

        if result.scheme == 'https' and resolved_ip:
            request.url = request.url.replace(
                'https://' + result.hostname,
                'https://' + resolved_ip,
            )
            connection_pool_kwargs['server_hostname'] = result.hostname
            connection_pool_kwargs['assert_hostname'] = result.hostname

            request.headers['Host'] = result.hostname
        else:
            connection_pool_kwargs.pop('server_hostname', None)
            connection_pool_kwargs.pop('assert_hostname', None)

        return super(HostHeaderSSLAdapter, self).send(request, **kwargs)


def thread_worker():
    while True:
        row = tasks_queue.get()
        if row is None:
            break
        process_row(row)
        tasks_queue.task_done()


def process_row(row):
    json_data = json.dumps(row)
    print(json_data)
    url = 'https://paulm-sony.test.edgekey.net/staging/upload'
    headers = {"Content-type": "application/json", "User-Agent": "paul-python"}
    requests.packages.urllib3.disable_warnings()
    session = requests.Session()
    session.mount('https://', HostHeaderSSLAdapter())
    response = session.post(url, data=json_data, headers=headers, verify=False)
    print(response.status_code, response.headers)


def start_threads(num_threads):
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=thread_worker)
        t.start()
        threads.append(t)
    return threads


def stop_threads(threads):
    for _ in threads:
        tasks_queue.put(None)
    for t in threads:
        t.join()


def main(file_name):
    if not file_name:
        print('File not found, no rules to upload')
        return

    num_threads = 3
    threads = start_threads(num_threads)

    with open(file_name, mode='r', newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        for row in reader:
            tasks_queue.put(row)

    tasks_queue.join()
    stop_threads(threads)


if __name__ == "__main__":
    main(file_name)
