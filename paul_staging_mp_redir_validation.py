import time
import pandas as pd
import requests
import dns.resolver
import hashlib
from urllib.parse import urlparse
import concurrent.futures
import sys


print("Waiting for 15 seconds for EKV to reach eventual consistency. Please be patient.", end='', flush=True)

for _ in range(15):  # Loop 15 times for 15 seconds
    time.sleep(1)  # Wait for 1 second
    print('.', end='', flush=True)  ## Print a dot for each second waited, without moving to a new line

print("\nDone waiting.")  # Move to a new line when done waiting


def _get_canonical_name(hostname_www):
    print(f'Attempting to get canonical name for {hostname_www}')
    resolver = dns.resolver.Resolver()
    try:
        canonical_name = resolver.resolve(hostname_www).canonical_name.to_unicode().rstrip('.')
        print(f'{hostname_www} has canonical name {canonical_name}')
        return canonical_name
    except dns.resolver.NXDOMAIN:
        print(f'Nonexistent domain {hostname_www}')
        return None


get_canonical_name = _get_canonical_name('paulm-sony.test.edgekey.net')
print(get_canonical_name)

staging_host = get_canonical_name.replace('akamaiedge', 'akamaiedge-staging')
print(staging_host)


def resolveDNSA():
    domain = staging_host
    resolver = dns.resolver.Resolver()
    answer = resolver.resolve(domain, "A")
    return answer


resultDNSA = resolveDNSA()
answerA = ''

for item in resultDNSA:
    resultant_str = ''.join([str(item), answerA])

#print(resultant_str)


class HostHeaderSSLAdapter(requests.adapters.HTTPAdapter):
    def resolve(self, hostname):
        ips = resultant_str
        resolutions = {'paulm-sony.test.edgekey.net': ips}
        #print(resolutions)
        return resolutions.get(hostname)

    def send(self, request, **kwargs):
        connection_pool_kwargs = self.poolmanager.connection_pool_kw
        result = urlparse(request.url)
        resolved_ip = self.resolve(result.hostname)

        if result.scheme == 'https' and resolved_ip:
            request.url = request.url.replace('https://' + result.hostname, 'https://' + resolved_ip)
            connection_pool_kwargs['server_hostname'] = result.hostname
            connection_pool_kwargs['assert_hostname'] = result.hostname
            request.headers['Host'] = result.hostname
        else:
            connection_pool_kwargs.pop('server_hostname', None)
            connection_pool_kwargs.pop('assert_hostname', None)

        return super(HostHeaderSSLAdapter, self).send(request, **kwargs)


def process_url(row):
    source_data = row['source']
    destination = row['destination']
    host = row['hostname']
    fRedirect = 'https://' + host + destination
    url = 'https://paulm-sony.test.edgekey.net' + source_data
    headers = {"Accept": "text/html"}

    session = requests.Session()
    session.mount('https://', HostHeaderSSLAdapter())
    response = session.get(url, headers=headers, allow_redirects=False)

    rresponse = response.status_code
    rlocation = response.headers.get('Location', None)
    source_hash = hashlib.sha256(source_data.encode('utf-8')).hexdigest()

    if rresponse != 301:
        print(f"Status code {rresponse} is incorrect for URL {url}, hash {source_hash}")
    elif rresponse == 301 and fRedirect != rlocation:
        print(f"Status code is correct, but the returned redirect {rlocation} is incorrect for incoming URL {url}")
        print(f"The correct redirect is {fRedirect}. Please review the rules {source_hash} uploaded to EKV")
    elif rresponse == 301 and fRedirect == rlocation:
        print("All good")


def main():
    file_name = "test-delete3.xlsx"
    df = pd.read_excel(file_name, engine='openpyxl')

    # Define the number of threads you want to use
    num_threads = 4  # For example, using 10 threads

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(process_url, row) for _, row in df.iterrows()]

        for future in concurrent.futures.as_completed(futures):
            future.result()  # This will raise exceptions if any occurred within a thread


if __name__ == "__main__":
    main()
