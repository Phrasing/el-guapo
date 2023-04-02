import imaplib
import email
import re
import chardet
import urllib.request
import aiohttp
import asyncio
import random
from bs4 import BeautifulSoup

IMAP_EMAIL = ""
IMAP_PASSWORD = ""

PROXY_LIST = []

USER_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36", 
               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36", 
               "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36", 
               "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36", 
               "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36"];

def load_proxies():
   with open('proxies.txt', 'r') as f:
       for line in f:
           PROXY_LIST.append(line.strip())

def zs2y(var0):
    var1 = ""
    var2 = [random.randint(0, 65535) for i in range(var0)]
    
    while var0 > 0:
        var0 -= 1
        var3 = 63 & var2[var0]
        var1 += str(base36encode(var3)) if var3 < 36 else (str(base36encode(var3 - 26)).upper() if var3 < 62 else ("_" if var3 < 63 else "-"))
    
    return var1

def base36encode(number):
    base36 = ""
    while number != 0:
        number, i = divmod(number, 36)
        base36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[i] + base36
    
    return base36 or "0"

async def extract_order_info(email_address, order_id):
    encoded_email = urllib.parse.quote(email_address)

    xo_id = zs2y(32)
    device_id = zs2y(36)
    
    order_info = {}

    url = f"http://www.walmart.com/orchestra/home/graphql/getGuestOrder/542f726b05eb80b2191d6582182d84fb3ed251b04f0fa53b66243fb0f4bc7440?variables=%7B%22orderId%22%3A%22{order_id}%22%2C%22emailAddress%22%3A%22{encoded_email}%22%7D"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/json",
        "x-o-segment": "oaoh",
        "x-o-platform-version": "main-1.58.0-a086a4-0324T0316",
        "x-o-correlation-id": xo_id,
        "wm_qos.correlation_id": xo_id,
        "WM_MP": "true",
        "x-o-ccm": "server",
        "x-o-gql-query": "query getGuestOrder",
        "X-APOLLO-OPERATION-NAME": "getGuestOrder",
        "x-latency-trace": "1",
        "x-enable-server-timing": "1",        
        "WM_PAGE_URL": "https://www.walmart.com/orders",
        "DEVICE_PROFILE_REF_ID": device_id,
        "x-o-platform": "rweb",
        "x-o-bu": "WALMART-US",
        "x-o-mart": "B2C",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache"
    }
    
    random_proxy = random.choice(PROXY_LIST)
    ip, port, user, password = random_proxy.split(':')
    
    formatted_proxy_http = f"http://{user}:{password}@{ip}:{port}"
    
    async with aiohttp.ClientSession() as session:
       async with session.get(url, headers=headers, cookies={"store": "USA"}, proxy=formatted_proxy_http) as response:
           if response.status != 200:
               print(await response.text())
               return
           data = await response.json()
 
           order_groups = data['data']['guestOrder']['groups_2101']
           grand_total = data['data']['guestOrder']['priceDetails']['grandTotal']['displayValue']
           
           tracking_numbers = []
           products = []
           
                   
           if order_groups is None:
               return
           for group in order_groups:
               if group is None:
                   continue
               if 'shipment' in group:
                   if group['shipment'] is None:
                       continue
                   if 'trackingNumber' in group['shipment']:
                       tracking_numbers.append(group['shipment']['trackingNumber'])
                       
               products = []  
               for item in group['items']:
                   product_name = item['productInfo']['name']
                   product_quantity = item['quantity']
                   products.append((product_name, product_quantity))
                
           order_info["products"] = products 
           order_info["tracking"] = tracking_numbers
           order_info["grand_total"] = grand_total
           order_info["order_number"] = order_id
          
           
    return order_info
            

    
def search_emails():
    orders = []

    imap_server = "imap.gmail.com"
    imap_port = 993

    mail = imaplib.IMAP4_SSL(imap_server, imap_port)
    mail.login(IMAP_EMAIL, IMAP_PASSWORD)

    mail.select("INBOX")

    search_criteria = 'SUBJECT "Shipped: items from order #"'
    _, data = mail.search(None, search_criteria)

    order_number_pattern = re.compile(r"Order number:\s*(\d+-\d+)")

    for num in data[0].split()[::-1]:
        _, email_data = mail.fetch(num, "(RFC822)")
        email_message = email.message_from_bytes(email_data[0][1])
        
        to_address = email_message['To']

        body = email_message.get_payload(decode=True)
        body_charset = email_message.get_content_charset()

        if not body_charset:
            body_charset = chardet.detect(body)["encoding"]

        body = body.decode(body_charset)

        order_number_match = order_number_pattern.search(body)
        order_number = order_number_match.group(
            1) if order_number_match else "Unknown"

        filtered_order_number = order_number.replace("-", "")
        orders.append((to_address, filtered_order_number))

    mail.close()
    mail.logout()

    return orders

async def main():
    tasks = []
    orders = search_emails()
    for email, order_number in orders:
        tasks.append(asyncio.create_task(extract_order_info(email, order_number)))
    orders_info = await asyncio.gather(*tasks)
    print(orders_info)

if __name__ == "__main__":
    load_proxies()
    asyncio.run(main())