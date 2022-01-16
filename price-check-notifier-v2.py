#credit: 
#1) https://www.youtube.com/watch?v=zAEfWiC_KBU&t=939s
#2) https://www.youtube.com/watch?v=B1IsCbXp0uE
#3) https://www.crummy.com/software/BeautifulSoup/bs4/doc/
#4) https://djangocentral.com/sending-emails-with-csv-attachment-using-python/
#5) https://www.geeksforgeeks.org/scraping-reddit-using-python/
#6) https://stackoverflow.com/questions/2602390/is-it-possible-for-beautifulsoup-to-work-in-a-case-insensitive-manner
#7) https://scipython.com/book2/chapter-4-the-core-python-language-ii/questions/sorting-a-list-containing-none/
#8) https://www.sqlite.org/datatype3.html
#9) https://stackoverflow.com/questions/44549167/construct-tuple-from-dictionary-values/44549210
#10) https://stackoverflow.com/questions/10913080/python-how-to-insert-a-dictionary-to-a-sqlite-database

import requests
import re
from bs4 import BeautifulSoup
import csv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from datetime import date
import praw
import sqlite3

#note: this script is meant to be run daily; hence, the reddit function searches daily posts

items_found = [] #going to be a list of dictionaries

def newegg(component):
	url = f"https://www.newegg.com/p/pl?d={component}"
	page = requests.get(url).text
	doc = BeautifulSoup(page, "html.parser")

	pages_raw = doc.find(class_="list-tool-pagination-text").strong #finds the page number (in the form "x/y" e.g. 1/4)
	pages = int(str(pages_raw).split("/")[-2].split(">")[-1][:-1]) #parses "x/y" to find the total number of pages

	for i in range(1, pages+1):
		today = date.today()

		url = f"https://www.newegg.com/p/pl?d={component}&page={i}"
		page = requests.get(url).text
		doc = BeautifulSoup(page, "html.parser")
		#there are several instances of this div so we use findAll to get all of them
		#the divs contain all the items on the page
		divs = doc.findAll(class_="item-cells-wrap border-cells items-grid-view four-cells expulsion-one-cell")
		for div in divs:
			# find all mentions of component in the div, re.I makes it case insensitive
			# isn't perfect though, e.g. isn't space insensitive (rx570 vs rx 570)
			items = div.find_all(string=re.compile(component, re.I))
			for item in items:
				parent = item.parent
				if parent.name != "a": #we want the href property of "a" tags only
					continue #go to the next item in the for loop
				next_parent = item.find_parent(class_="item-container")
				price_strong = next_parent.find(class_="price-current").strong
				if price_strong is not None: #some of these products don't have prices so we skip them
					link = parent['href']
					price = price_strong.text
					items_found.append({"item": item, "price ($)": int(price.replace(",","")), "link": link, "source": "Newegg", "date": today})
	#example output: {'item': 'XFX Radeon RX 570 8GB DDR5 PCI Express 3.0 CrossFireX Support Video Card RX-570P8DFD6', 'price ($)': 599, 'link': 'https://www.newegg.com/xfx-radeon-rx-570-rx-570p8dfd6/p/N82E16814150815?Description=570&cm_re=570-_-14-150-815-_-Product', 'source': 'Newegg'}

def reddit(component):
	today = date.today()
	# There are 2 types of PRAW instances: read-only and authorized. We only need to read.
	reddit_read_only = praw.Reddit(client_id="CLIENT_ID",  # your client id
								   client_secret="CLIENT_SECRET",  # your client secret
								   user_agent="NAME OF YOUR PROGRAM")  # your user agent
	# Extracting information from r/buildapcsales and adding it to items_found
	subreddit = reddit_read_only.subreddit("buildapcsales")
	for post in subreddit.top("day"):
		if component.lower() in post.title.lower(): #case-insensitive
			# setting price = None because reddit post titles are irregular and the prices are hard to extract
			# e.g. there might be a shipping cost e.g. "$580 + $7.52 shipping" or mail-in rebates
			# I'll just let the user figure it out
			items_found.append({"item": post.title, "price ($)": None, "link": post.url, "source": "r/buildapcsales", "date": today})

def email_alert(items_found, component, to):
	#sorting items_found by price 
	items_found = sorted(items_found, key = lambda i: (i['price ($)'] is None, i['price ($)']))
	#since the fields are the same for each dictionary in items_found, I can just take the field names from one dictionary
	field_names = [key for key in items_found[0]]
	#writing items_found to a csv to send by email
	with open('price_check_output.csv', 'w') as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames=field_names)
		writer.writeheader()
		writer.writerows(items_found)

	msg = MIMEMultipart()
	user = "EMAIL YOU WANT TO SEND FROM"
	password = "PASSWORD (SEE CREDIT SOURCE 2 ABOVE)"
	msg['from'] = user
	msg['subject'] = f"PC Component Report: {date.today().strftime('%B %d %Y')}"
	msg['to'] = to

	body_part = MIMEText(f"Here is today's report on prices for: {component}", 'plain')
	msg.attach(body_part) #attach body to email
	# open and read the CSV file in binary
	with open('price_check_output.csv','rb') as file:
		msg.attach(MIMEApplication(file.read(), Name='price_check_output.csv')) #attach file to email

	server = smtplib.SMTP("smtp.gmail.com", 587)
	server.starttls()
	server.login(user, password)

	server.sendmail(msg['from'], msg['to'], msg.as_string())
	server.quit()

	print("~ email sent ~")

def main():
	component = input("What part are you searching for? ")
	newegg(component)
	reddit(component)
	email_alert(items_found, component, "EMAIL YOU WANT TO SEND TO")

	# connects to or creates (if doesn't exist) a database
	conn = sqlite3.connect('price-check-notifier-v2.db')
	c = conn.cursor()
	# NOTE: for some reason, you can't name the column "price ($)"; the parentheses must cause some issue
	c.execute("""CREATE TABLE IF NOT EXISTS all_items (items TEXT, price_$ INT, link TEXT, source TEXT, date DATE);""")
	items_found_converted = [(i["item"], i["price ($)"], i["link"], i["source"], i["date"]) for i in items_found]
	c.executemany("INSERT INTO all_items VALUES (?,?,?,?,?)", items_found_converted)
	conn.commit()
	print("~ sql insert complete ~")
	conn.close()

if __name__=='__main__':
	main()