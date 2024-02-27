import asyncio
import pandas as pd
import dns.resolver
import hashlib
from aiohttp import ClientSession, TCPConnector
import ssl

# Function to get the canonical name
async def get_canonical_name(hostname):
    resolver = dns.resolver.Resolver()
    try:
        answer = resolver.resolve(hostname, 'CNAME')
        canonical_name = str(answer[0].target).rstrip('.')
        return canonical_name
    except dns.resolver.NoAnswer:
        return hostname

# Function to resolve DNS A record
async def resolve_dns_a_record(hostname):
    resolver = dns.resolver.Resolver()
    answer = resolver.resolve(hostname, "A")
    ips = [str(item) for item in answer]
    return ips[0]  # Return the first IP address

# Process URL
async def process_url(row, session, ip_address):
    source_data = row['source']
    destination = row['destination']
    host = row['hostname']
    fRedirect = 'https://' + host + destination
    url = f'https://{ip_address}' + source_data
    headers = {"Accept": "text/html", "Host": "paulm-sony.test.edgekey.net"}

    async with session.get(url, headers=headers, allow_redirects=False) as response:
        rresponse = response.status
        rlocation = response.headers.get('Location', None)
        source_hash = hashlib.sha256(source_data.encode('utf-8')).hexdigest()

        if rresponse != 301:
            print(f"Status code {rresponse} is incorrect for URL {url}, hash {source_hash}")
        elif rresponse == 301 and fRedirect != rlocation:
            print(f"Status code is correct, but the returned redirect {rlocation} is incorrect for incoming URL {url}")
            print(f"The correct redirect is {fRedirect}. Please review the rules {source_hash} uploaded to EKV")
        elif rresponse == 301 and fRedirect == rlocation:
            print("All good")

# Main async function
async def main():
    file_name = "test-uploader2.xlsx"
    df = pd.read_excel(file_name, engine='openpyxl')

    # Perform DNS resolution once for the canonical name
    canonical_name = await get_canonical_name('paulm-sony.test.edgekey.net')
    staging_host = canonical_name.replace('akamaiedge', 'akamaiedge-staging')
    ip_address = await resolve_dns_a_record(staging_host)

    # SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = TCPConnector(ssl=ssl_context)
    async with ClientSession(connector=connector) as session:
        tasks = [process_url(row, session, ip_address) for index, row in df.iterrows()]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
